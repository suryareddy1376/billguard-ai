"""
Layer 3A — Feature Engineering
Computes all explicit, deterministic features for each line item.

FIXES (v2):
  - z-score returns None when IQR=0 (mathematically undefined, not zero)
  - duplicate_count removes quantity from the key (two identical MRIs are dupes regardless of qty)
  - category_mismatch no longer flags every UNKNOWN item blindly
"""
import json
from pathlib import Path
from collections import Counter

# Load tariff data (Layer 5 — Tariff & Benchmarking Service)
_TARIFF_PATH = Path(__file__).parent.parent / "tariff" / "cghs_rates.json"
with open(_TARIFF_PATH) as f:
    TARIFF = json.load(f)


def get_benchmark(procedure_code: str) -> dict:
    return TARIFF.get(procedure_code) or TARIFF["UNKNOWN"]


def compute_features(item: dict, all_items: list[dict]) -> dict:
    """
    Returns a features dict for a single line item.
    all_items = full canonical line_items list for duplicate/frequency checks.
    """
    features = {}
    code = item.get("procedure_code", "UNKNOWN")
    unit_price = item.get("unit_price")
    benchmark = get_benchmark(code)
    p50 = benchmark["p50"]

    # 1. price_deviation_percentage
    if unit_price is not None and p50 is not None and p50 > 0:
        features["price_deviation_percentage"] = round(((unit_price - p50) / p50) * 100, 2)
    else:
        features["price_deviation_percentage"] = None

    # Always store benchmark data
    features["benchmark_p50"] = p50
    features["benchmark_p25"] = benchmark["p25"]
    features["benchmark_p75"] = benchmark["p75"]
    features["benchmark_source"] = benchmark["source"]

    # 2. duplicate_count — exact (procedure_code|raw_desc, date) match
    # Removed quantity from key: two identical MRIs are dupes regardless of qty
    if item["procedure_code"] == "UNKNOWN":
        dupe_key = (item["raw_description"].lower().strip(), item.get("date_of_service", ""))
        all_keys = [
            (i["raw_description"].lower().strip(), i.get("date_of_service", ""))
            for i in all_items if i["procedure_code"] == "UNKNOWN"
        ]
    else:
        dupe_key = (item["procedure_code"], item.get("date_of_service", ""))
        all_keys = [
            (i["procedure_code"], i.get("date_of_service", ""))
            for i in all_items
        ]
    features["duplicate_count"] = max(0, all_keys.count(dupe_key) - 1)  # exclude self

    # 3. service_frequency — how many times this category appears in the bill
    cat_counts = Counter(i["mapped_category"] for i in all_items)
    features["service_frequency"] = cat_counts.get(item["mapped_category"], 1)

    # 4. category_mismatch — only flag if the description contains strong keywords
    # from a DIFFERENT known category (suggesting miscategorization, not just "unknown")
    features["category_mismatch"] = _check_category_mismatch(
        item["raw_description"], item["mapped_category"]
    )

    # 5. unit_price_outlier_z — z-score vs simple benchmark distribution
    features["unit_price_outlier_z"] = _compute_z(unit_price, benchmark)

    # 6. invalid_combo_flag — set at rules engine level, defaulting to False here
    features["invalid_combo_flag"] = False

    # 7. has_data_quality_flags
    features["has_quality_issues"] = len(item.get("data_quality_flags", [])) > 0
    features["data_quality_flags"] = item.get("data_quality_flags", [])

    return features


def _check_category_mismatch(raw_desc: str, mapped_category: str) -> bool:
    """
    Only flag a mismatch if a known category's strong keyword appears in the
    description but the item was mapped to a DIFFERENT category or UNKNOWN.
    Prevents blindly flagging every UNKNOWN item.
    """
    from layers.normalization import CATEGORY_LOOKUP
    desc_lower = raw_desc.lower()

    for entry in CATEGORY_LOOKUP:
        if any(kw in desc_lower for kw in entry["keywords"]):
            # Description matches this category's keywords
            if mapped_category != entry["category"]:
                return True  # Mapped to wrong category
            return False  # Correctly mapped

    # No known keywords found — not a mismatch, just unrecognized
    return False


def _compute_z(price: float | None, benchmark: dict) -> float | None:
    """
    Approximate z-score using IQR-based std estimate:
    sigma ≈ (p75 - p25) / 1.35  (normal distribution approximation)

    Returns None when IQR=0 (mathematically undefined, not zero).
    """
    if price is None:
        return None
    p50 = benchmark["p50"]
    p25 = benchmark["p25"]
    p75 = benchmark["p75"]
    iqr = p75 - p25
    if iqr <= 0:
        return None  # Cannot compute z-score without spread
    sigma = iqr / 1.35
    z = (price - p50) / sigma
    return round(z, 3)
