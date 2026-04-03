"""
Layer 3D — Weighted Score Aggregator
Combines rule violations + anomaly signals into a single fraud_score [0, 100].

SCORING FORMULA (v2 — normalized):
  base_points     = sum of deduplicated weighted violations/signals
  item_ratio      = flagged_items / total_items          (0.0–1.0)
  severity_factor = 0.4 + 0.6 × item_ratio              (0.4–1.0)
  final_score     = clamp(base_points × severity_factor, 0, 100)

This ensures:
  - A single overpriced item in a 12-item bill doesn't spike to CRITICAL
  - A bill where 10/12 items are overpriced scores proportionally higher
  - Score maintains meaningful granularity across 0–100
  - The formula is fully deterministic and auditable

OVERCHARGE FORMULA:
  overcharge = max(0, unit_price − p75) × quantity
  Uses p75 (75th percentile) as the "fair upper bound" — defensible standard.

RISK THRESHOLDS:
  0–30   → LOW
  31–60  → MODERATE
  61–85  → HIGH
  86–100 → CRITICAL
"""

# ---------------------------------------------------------------------------
# Weight table — configurable per deployment
# ---------------------------------------------------------------------------
RULE_WEIGHTS = {
    "HIGH": 25,
    "MEDIUM": 15,
    "LOW": 5,
}

SIGNAL_WEIGHTS = {
    "S01_Z_CRITICAL": 20,
    "S01_Z_MODERATE": 12,
    "S02_PRICE_HIGH": 18,
    "S02_PRICE_MEDIUM": 10,
    "S03_CATEGORY_MISMATCH": 5,
    "S04_HIGH_QTY": 8,
    "S05_UNDERPRICED": 10,
}

DATA_QUALITY_DISCOUNT = 0.30      # 30% weight discount if item has quality issues
UNKNOWN_CATEGORY_DISCOUNT = 0.50  # 50% weight discount for UNKNOWN category items
UNKNOWN_MAX_CONTRIBUTION = 20     # Max total score contribution from UNKNOWN items
MAX_SCORE = 100

RISK_LABELS = [
    (86, "CRITICAL"),
    (61, "HIGH"),
    (31, "MODERATE"),
    (0,  "LOW"),
]


def aggregate_score(
    rule_violations: list[dict],
    anomaly_signals: list[dict],
    items_with_features: list[dict],
) -> dict:
    """
    Returns:
    {
      fraud_score: float,
      risk_label: str,
      confidence: float,
      score_breakdown: [{source, item_id, weight, reason}],
      total_overcharge_estimate: float,
    }
    """
    raw_score = 0.0
    unknown_score = 0.0
    breakdown = []
    total_items = len(items_with_features)

    # Build quality-issues lookup
    quality_items = {
        entry["item"]["item_id"]
        for entry in items_with_features
        if entry["features"].get("has_quality_issues")
    }

    # Build UNKNOWN items lookup
    unknown_items = {
        entry["item"]["item_id"]
        for entry in items_with_features
        if entry["item"].get("mapped_category") == "UNKNOWN"
    }

    # --- Score rule violations ---
    # Deduplicate: only score each (item_id, rule_id) pair once
    seen_rule_keys = set()
    for v in rule_violations:
        item_id = v.get("item_id", "bill-level")
        rule_id = v.get("rule_id", "UNKNOWN")
        dedup_key = (item_id, rule_id)

        if dedup_key in seen_rule_keys:
            continue
        seen_rule_keys.add(dedup_key)

        weight = RULE_WEIGHTS.get(v["severity"], 5)
        if item_id in quality_items:
            weight = weight * (1 - DATA_QUALITY_DISCOUNT)
        if item_id in unknown_items:
            weight = weight * (1 - UNKNOWN_CATEGORY_DISCOUNT)

        if item_id in unknown_items:
            unknown_score += weight
        else:
            raw_score += weight

        breakdown.append({
            "source": "RULE",
            "rule_id": rule_id,
            "item_id": item_id,
            "weight": round(weight, 1),
            "reason": v["description"],
        })

    # --- Score anomaly signals ---
    seen_signal_keys = set()
    for sig in anomaly_signals:
        item_id = sig.get("item_id", "bill-level")
        signal_type = sig.get("signal_type", "UNKNOWN")
        dedup_key = (item_id, signal_type)

        if dedup_key in seen_signal_keys:
            continue
        seen_signal_keys.add(dedup_key)

        weight = SIGNAL_WEIGHTS.get(signal_type, 5)
        if item_id in quality_items:
            weight = weight * (1 - DATA_QUALITY_DISCOUNT)
        if item_id in unknown_items:
            weight = weight * (1 - UNKNOWN_CATEGORY_DISCOUNT)

        if item_id in unknown_items:
            unknown_score += weight
        else:
            raw_score += weight

        breakdown.append({
            "source": "STATISTICAL",
            "signal_type": signal_type,
            "item_id": item_id,
            "weight": round(weight, 1),
            "reason": sig["description"],
        })

    # Cap UNKNOWN contribution
    capped_unknown = min(unknown_score, UNKNOWN_MAX_CONTRIBUTION)
    base_points = raw_score + capped_unknown

    # --- Normalize using saturation curve + item ratio ---
    # Step 1: Collect unique flagged item IDs
    flagged_item_ids = set()
    for v in rule_violations:
        flagged_item_ids.add(v.get("item_id"))
    for s in anomaly_signals:
        flagged_item_ids.add(s.get("item_id"))
    flagged_item_ids.discard(None)
    flagged_item_ids.discard("bill-level")

    flagged_count = len(flagged_item_ids)
    item_ratio = flagged_count / total_items if total_items > 0 else 0.0

    # Step 2: Apply logarithmic saturation curve
    # Maps base_points to 0-100 with diminishing returns:
    #   30 pts -> ~31,  50 pts -> ~46,  80 pts -> ~63
    #  120 pts -> ~78, 185 pts -> ~90, 370 pts -> ~99
    import math
    SATURATION_K = 80  # Controls steepness: higher = more gradual saturation
    saturated = 100 * (1 - math.exp(-base_points / SATURATION_K))

    # Step 3: Apply item ratio factor (0.5 to 1.0)
    # Bills where only 1 out of 12 items is flagged get dampened
    severity_factor = 0.5 + 0.5 * item_ratio
    final_score = saturated * severity_factor

    final_score = min(final_score, MAX_SCORE)
    final_score = max(0.0, final_score)

    # Risk label
    risk_label = "LOW"
    for threshold, label in RISK_LABELS:
        if final_score >= threshold:
            risk_label = label
            break

    # --- Confidence score ---
    confidence = _compute_confidence(items_with_features, unknown_items, quality_items)

    # Overcharge estimate
    overcharge_estimate = _compute_overcharge(items_with_features)

    return {
        "fraud_score": round(final_score, 1),
        "risk_label": risk_label,
        "confidence": round(confidence, 2),
        "score_breakdown": breakdown,
        "total_overcharge_estimate": overcharge_estimate,
    }


def _compute_confidence(
    items_with_features: list[dict],
    unknown_items: set,
    quality_items: set,
) -> float:
    """
    Confidence score (0.0–1.0) reflecting data quality:
      1.0 = all items categorized, no quality issues, all have prices
      0.0 = all items unknown, all have quality issues, none have prices

    Formula:
      confidence = 1.0
        − 0.35 × unknown_ratio
        − 0.25 × quality_issue_ratio
        − 0.20 × missing_price_ratio
        − 0.20 × missing_benchmark_ratio
    Clamped to [0.1, 1.0]
    """
    total = len(items_with_features)
    if total == 0:
        return 0.5  # No data = uncertain

    unknown_ratio = len(unknown_items) / total
    quality_ratio = len(quality_items) / total

    missing_price_count = sum(
        1 for e in items_with_features
        if e["item"].get("unit_price") is None
    )
    missing_price_ratio = missing_price_count / total

    missing_benchmark_count = sum(
        1 for e in items_with_features
        if e["features"].get("benchmark_source") == "FALLBACK"
    )
    missing_benchmark_ratio = missing_benchmark_count / total

    confidence = (
        1.0
        - 0.35 * unknown_ratio
        - 0.25 * quality_ratio
        - 0.20 * missing_price_ratio
        - 0.20 * missing_benchmark_ratio
    )
    return max(0.1, min(1.0, confidence))


def _compute_overcharge(items_with_features: list[dict]) -> float:
    """
    Estimates total potential overcharge.
    Formula: overcharge = max(0, unit_price − p75) × quantity
    Uses p75 (75th percentile) as the 'fair upper bound'.
    """
    total = 0.0
    for entry in items_with_features:
        item = entry["item"]
        feat = entry["features"]
        unit_price = item.get("unit_price")
        p75 = feat.get("benchmark_p75")
        qty = item.get("quantity", 1) or 1

        if unit_price is not None and p75 is not None and unit_price > p75:
            over = (unit_price - p75) * qty
            total += over
    return round(total, 2)
