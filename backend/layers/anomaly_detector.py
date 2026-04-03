"""
Layer 3C — Statistical Anomaly Detection
Uses z-score and distribution thresholds to detect price outliers and frequency anomalies.
No ML required — purely statistical, explainable, works with zero training data.

FIXES (v2):
  - Added S05: underpricing detection (catches unbundling fraud)
  - Guard against None z-scores (from IQR=0 cases)
  - Improved threshold labels for consistency
"""

# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------
Z_THRESHOLD_HIGH = 3.0      # |z| > 3.0 → HIGH anomaly
Z_THRESHOLD_MED = 2.0       # |z| > 2.0 → MEDIUM anomaly
PRICE_DEVIATION_HIGH = 150  # > 150% above median → HIGH
PRICE_DEVIATION_MED = 75    # > 75% above median → MEDIUM
PRICE_UNDERPRICED = -60     # < -60% below median → suspicious underpricing


def run_anomaly_detection(items_with_features: list[dict]) -> list[dict]:
    """
    items_with_features: list of { item, features } dicts
    Returns anomaly_signals: [{ item_id, signal_type, severity, value, threshold, description }]
    """
    signals = []

    for entry in items_with_features:
        item = entry["item"]
        feat = entry["features"]
        item_id = item["item_id"]
        desc = item["raw_description"]
        unit_price = item.get("unit_price")

        # --- Signal S01: Price Z-Score Outlier ---
        z = feat.get("unit_price_outlier_z")
        if z is not None:
            abs_z = abs(z)
            if abs_z > Z_THRESHOLD_HIGH:
                signals.append({
                    "signal_type": "S01_Z_CRITICAL",
                    "severity": "HIGH",
                    "item_id": item_id,
                    "value": round(z, 2),
                    "threshold": Z_THRESHOLD_HIGH,
                    "description": (
                        f"'{desc}' has an extreme price deviation "
                        f"(z-score: {z:+.2f}). This is well outside the normal distribution for this procedure."
                    ),
                })
            elif abs_z > Z_THRESHOLD_MED:
                signals.append({
                    "signal_type": "S01_Z_MODERATE",
                    "severity": "MEDIUM",
                    "item_id": item_id,
                    "value": round(z, 2),
                    "threshold": Z_THRESHOLD_MED,
                    "description": (
                        f"'{desc}' has a notable price deviation "
                        f"(z-score: {z:+.2f}). Above the typical range for this procedure."
                    ),
                })

        # --- Signal S02: Price Deviation % (overpricing) ---
        deviation = feat.get("price_deviation_percentage")
        p50 = feat.get("benchmark_p50")
        if deviation is not None and unit_price is not None and deviation > 0:
            if deviation > PRICE_DEVIATION_HIGH:
                signals.append({
                    "signal_type": "S02_PRICE_HIGH",
                    "severity": "HIGH",
                    "item_id": item_id,
                    "value": round(deviation, 1),
                    "threshold": PRICE_DEVIATION_HIGH,
                    "description": (
                        f"'{desc}' charged at ₹{unit_price:,.0f}, which is "
                        f"{deviation:.0f}% above the regional median of ₹{p50:,.0f}."
                    ),
                })
            elif deviation > PRICE_DEVIATION_MED:
                signals.append({
                    "signal_type": "S02_PRICE_MEDIUM",
                    "severity": "MEDIUM",
                    "item_id": item_id,
                    "value": round(deviation, 1),
                    "threshold": PRICE_DEVIATION_MED,
                    "description": (
                        f"'{desc}' charged at ₹{unit_price:,.0f}, which is "
                        f"{deviation:.0f}% above the regional median of ₹{p50:,.0f}."
                    ),
                })

        # --- Signal S03: Category Mismatch ---
        if feat.get("category_mismatch"):
            signals.append({
                "signal_type": "S03_CATEGORY_MISMATCH",
                "severity": "LOW",
                "item_id": item_id,
                "value": 1,
                "threshold": 0,
                "description": (
                    f"'{desc}' appears to match a known medical category "
                    f"but was mapped differently. Manual review recommended."
                ),
            })

        # --- Signal S04: Suspiciously High Quantity ---
        qty = item.get("quantity", 1)
        if qty > 10 and item["mapped_category"] not in ("PHARMACY", "CONSUMABLE"):
            signals.append({
                "signal_type": "S04_HIGH_QTY",
                "severity": "MEDIUM",
                "item_id": item_id,
                "value": qty,
                "threshold": 10,
                "description": (
                    f"'{desc}' has a quantity of {qty:.0f}, which is unusually high "
                    f"for a procedure in category '{item['mapped_category']}'."
                ),
            })

        # --- Signal S05: Suspicious Underpricing ---
        # Catches unbundling fraud where a surgery or procedure is suspiciously cheap
        if (deviation is not None
                and unit_price is not None
                and deviation < PRICE_UNDERPRICED
                and item["mapped_category"] not in ("PHARMACY", "CONSUMABLE", "UNKNOWN")
                and unit_price > 0):
            signals.append({
                "signal_type": "S05_UNDERPRICED",
                "severity": "MEDIUM",
                "item_id": item_id,
                "value": round(deviation, 1),
                "threshold": PRICE_UNDERPRICED,
                "description": (
                    f"'{desc}' charged at ₹{unit_price:,.0f}, which is "
                    f"{abs(deviation):.0f}% below the regional median of ₹{p50:,.0f}. "
                    f"This may indicate unbundling or billing error."
                ),
            })

    return signals
