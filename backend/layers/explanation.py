"""
Layer 3E — Explanation Generator
Produces plain-language explanations for each flagged item.
Template-based, deterministic. No LLM required.

FIXES (v2):
  - LOW risk summary now acknowledges overcharges if they exist
  - Explanations are evidence-based and never contradict actual numbers
  - Added confidence caveat when confidence is low
"""


def generate_item_explanations(
    item: dict,
    features: dict,
    rule_violations: list[dict],
    anomaly_signals: list[dict],
) -> list[str]:
    """Returns a list of plain-language explanation strings for a single item."""
    explanations = []
    item_id = item["item_id"]
    desc = item["raw_description"]
    unit_price = item.get("unit_price")
    quantity = item.get("quantity", 1)
    p50 = features.get("benchmark_p50")
    p25 = features.get("benchmark_p25")
    p75 = features.get("benchmark_p75")
    source = features.get("benchmark_source", "benchmark data")

    # From rule violations
    item_violations = [v for v in rule_violations if v.get("item_id") == item_id]
    for v in item_violations:
        explanations.append(v["description"])

    # From anomaly signals — produce rich, concrete explanations
    item_signals = [s for s in anomaly_signals if s.get("item_id") == item_id]
    for sig in item_signals:
        t = sig["signal_type"]

        if t in ("S02_PRICE_HIGH", "S02_PRICE_MEDIUM") and unit_price and p50:
            dev = features.get("price_deviation_percentage", 0)
            explanations.append(
                f"'{desc}' was charged at ₹{unit_price:,.0f}, which is {abs(dev):.0f}% "
                f"{'above' if dev > 0 else 'below'} the regional median of ₹{p50:,.0f} "
                f"(based on {source}). Fair price range: ₹{p25:,.0f}–₹{p75:,.0f}."
            )

        elif t in ("S01_Z_CRITICAL", "S01_Z_MODERATE"):
            z = features.get("unit_price_outlier_z", 0)
            if z is not None:
                explanations.append(
                    f"'{desc}' is statistically unusual for its category "
                    f"(deviation score: {z:+.1f}). Prices in this range are seen in fewer than "
                    f"{'2%' if abs(z) > 3 else '5%'} of similar bills."
                )

        elif t == "S03_CATEGORY_MISMATCH":
            explanations.append(
                f"'{desc}' appears to match a known medical procedure category "
                f"but was mapped differently. This may indicate an unusual billing code "
                f"or a data entry error. Recommend requesting an itemized clarification from the hospital."
            )

        elif t == "S04_HIGH_QTY":
            explanations.append(
                f"'{desc}' was billed {quantity:.0f} times, which is unusually high "
                f"for a procedure of this type. Please verify this quantity with your discharge summary."
            )

        elif t == "S05_UNDERPRICED":
            explanations.append(
                f"'{desc}' was charged at ₹{unit_price:,.0f}, which is significantly below "
                f"the expected median of ₹{p50:,.0f}. This may indicate unbundling "
                f"(splitting a procedure into smaller charges) or a billing data error."
            )

    # Data quality caveats
    flags = features.get("data_quality_flags", [])
    if "PRICE_INFERRED" in flags:
        explanations.append(
            f"Note: The unit price for '{desc}' was inferred from the total amount and quantity, "
            f"as it was not stated explicitly. Accuracy may vary."
        )
    if "OCR_LOW_CONFIDENCE" in flags:
        explanations.append(
            f"Note: '{desc}' was extracted via OCR with low confidence. "
            f"Please cross-check with the original paper bill."
        )
    if "EXTRACTED_VIA_NLP" in flags:
        explanations.append(
            f"Note: This item was extracted from a scanned bill image using OCR. "
            f"The description and price may not be perfectly accurate. "
            f"Please verify against the original bill."
        )

    return explanations


def generate_summary_explanation(
    fraud_score: float,
    risk_label: str,
    total_overcharge: float,
    flagged_count: int,
    total_count: int,
    unknown_ratio: float = 0.0,
    confidence: float = 1.0,
) -> str:
    """Generates a bill-level plain-language summary."""
    # OCR quality caveat
    ocr_caveat = ""
    if unknown_ratio > 0.5:
        ocr_caveat = (
            " Note: A significant portion of this bill could not be automatically categorized, "
            "which may be due to OCR extraction quality. The fraud score may be less reliable. "
            "We recommend manual review of the original bill."
        )

    # Confidence caveat
    confidence_caveat = ""
    if confidence < 0.5:
        confidence_caveat = (
            f" Analysis confidence is {confidence:.0%} due to limited data quality. "
            "Results should be interpreted with caution."
        )

    if risk_label == "LOW":
        if total_overcharge > 0:
            return (
                f"Your bill appears largely consistent with expected rates. "
                f"{flagged_count} out of {total_count} items were flagged for minor review. "
                f"Minor potential overcharges of ₹{total_overcharge:,.0f} were detected, "
                f"but they fall within acceptable variation.{confidence_caveat}{ocr_caveat}"
            )
        return (
            f"Your bill appears largely consistent with expected rates. "
            f"{flagged_count} out of {total_count} items were flagged for minor review. "
            f"No significant overcharges were detected.{confidence_caveat}{ocr_caveat}"
        )
    elif risk_label == "MODERATE":
        return (
            f"Your bill has some items that appear above typical market rates. "
            f"{flagged_count} out of {total_count} items were flagged. "
            f"Estimated potential overcharge: ₹{total_overcharge:,.0f}. "
            f"We recommend reviewing the highlighted items before paying.{confidence_caveat}{ocr_caveat}"
        )
    elif risk_label == "HIGH":
        return (
            f"Your bill contains several discrepancies. {flagged_count} out of {total_count} items "
            f"are priced significantly above regional benchmarks or show unusual billing patterns. "
            f"Estimated potential overcharge: ₹{total_overcharge:,.0f}. "
            f"Consider requesting an itemized bill from the hospital and disputing flagged charges.{confidence_caveat}{ocr_caveat}"
        )
    elif risk_label == "CRITICAL":
        return (
            f"CRITICAL: Your bill shows strong signs of overcharging or billing fraud. "
            f"{flagged_count} out of {total_count} items triggered high-severity alerts. "
            f"Estimated excess charges: ₹{total_overcharge:,.0f}. "
            f"We strongly recommend disputing this bill and filing a complaint with your "
            f"insurer or the hospital ombudsman.{confidence_caveat}{ocr_caveat}"
        )
    return f"Analysis complete.{confidence_caveat}{ocr_caveat}"
