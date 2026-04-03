"""
Layer 3B — Rules Engine
Hardcoded + configurable deterministic checks.
Returns a list of rule violations per bill.

FIXES (v2):
  - R01: Fires once per duplicate GROUP, not once per item (prevents O(N²) inflation)
  - R02: Only flags the EXCESS items beyond the frequency cap
  - R04: Explicitly handles zero/negative prices
  - R06: Uses a more reasonable threshold
"""
from collections import defaultdict

# ---------------------------------------------------------------------------
# Rule: Invalid Procedure Combinations
# These pairs cannot co-exist on the same date for the same patient.
# ---------------------------------------------------------------------------
INVALID_COMBOS = [
    ("ANAES_GEN", "CARD_ECG"),        # Anaesthesia + routine ECG same day unlikely valid together as separate charges
    ("RAD_MRI", "RAD_CT"),            # Both MRI and CT of same body part on same day (body part check simplified)
    ("ICU_DAY", "ROOM_DAY"),          # Cannot charge both ICU and general room on same day
]

# ---------------------------------------------------------------------------
# Rule: Maximum allowed quantity per procedure per bill
# ---------------------------------------------------------------------------
MAX_FREQUENCY = {
    "PATH_CBC": 2,       # CBC more than 2x per day is unusual
    "PATH_GLUCOSE": 4,   # Blood sugar up to 4x/day is ok
    "CONS_DOC": 3,       # More than 3 doctor consultations per day is suspicious
    "RAD_MRI": 1,        # Only 1 MRI per bill episode expected
    "RAD_CT": 2,         # Max 2 CT scans per episode
    "ANAES_GEN": 1,      # Only 1 anaesthesia per surgery
}

# ---------------------------------------------------------------------------
# Rule: Price floor checks (implausibly low, may indicate fraud too)
# ---------------------------------------------------------------------------
PRICE_FLOOR = {
    "SURG_GEN": 5000,
    "ANAES_GEN": 1000,
    "ICU_DAY": 500,
}


def run_rules_engine(canonical_bill: dict) -> list[dict]:
    """
    Returns list of rule_violation objects:
    { rule_id, severity, item_id, description }
    """
    violations = []
    items = canonical_bill.get("line_items", [])

    if not items:
        return violations

    # Build index: procedure_code → list of items
    code_map = defaultdict(list)
    for item in items:
        code_map[item["procedure_code"]].append(item)

    # --- Rule R01: Duplicate Line Items ---
    # Fire ONCE per duplicate group, not once per item.
    # A "group" = items sharing the same (procedure_code|raw_desc, date, qty).
    seen_groups = set()
    for item in items:
        item_id = item["item_id"]
        code = item["procedure_code"]
        quantity = item.get("quantity", 1)

        if code == "UNKNOWN":
            group_key = (
                item["raw_description"].lower().strip(),
                item.get("date_of_service", ""),
            )
            dupes = [i for i in items if (
                i["procedure_code"] == "UNKNOWN" and
                i["raw_description"].lower().strip() == item["raw_description"].lower().strip() and
                i.get("date_of_service") == item.get("date_of_service") and
                i["item_id"] != item_id
            )]
        else:
            group_key = (
                code,
                item.get("date_of_service", ""),
            )
            dupes = [i for i in items if (
                i["procedure_code"] == code and
                i.get("date_of_service") == item.get("date_of_service") and
                i["item_id"] != item_id
            )]

        if dupes and group_key not in seen_groups:
            seen_groups.add(group_key)
            dupe_count = len(dupes) + 1  # include self
            violations.append({
                "rule_id": "R01_DUPLICATE",
                "severity": "HIGH",
                "item_id": item_id,  # representative item
                "description": (
                    f"Duplicate charge detected: '{item['raw_description']}' "
                    f"appears {dupe_count} times on the same date."
                ),
            })

    # --- Rule R02: Frequency Cap per Procedure ---
    # Only fire ONCE per procedure code, and only if count > max.
    for code, max_freq in MAX_FREQUENCY.items():
        group = code_map.get(code, [])
        if len(group) > max_freq:
            # Flag the first excess item only (representative)
            representative = group[max_freq]  # the first item beyond the cap
            violations.append({
                "rule_id": "R02_FREQUENCY_CAP",
                "severity": "MEDIUM",
                "item_id": representative["item_id"],
                "description": (
                    f"'{representative['raw_description']}' appears {len(group)} times; "
                    f"expected max {max_freq} per bill episode."
                ),
            })

    for item in items:
        item_id = item["item_id"]
        code = item["procedure_code"]
        unit_price = item.get("unit_price")

        # --- Rule R03: Price Floor ---
        floor = PRICE_FLOOR.get(code)
        if floor and unit_price is not None and unit_price > 0 and unit_price < floor:
            violations.append({
                "rule_id": "R03_PRICE_FLOOR",
                "severity": "LOW",
                "item_id": item_id,
                "description": (
                    f"Unit price ₹{unit_price:,.0f} for '{item['raw_description']}' "
                    f"is below expected minimum of ₹{floor:,.0f}. "
                    f"Possible undercoding or data error."
                ),
            })

        # --- Rule R04: Zero or Negative Price ---
        if unit_price is not None and unit_price <= 0:
            violations.append({
                "rule_id": "R04_ZERO_PRICE",
                "severity": "MEDIUM",
                "item_id": item_id,
                "description": (
                    f"'{item['raw_description']}' has a zero or negative unit price "
                    f"(₹{unit_price}). Possible billing error."
                ),
            })

    # --- Rule R05: Invalid Procedure Combinations ---
    present_codes = set(code_map.keys())
    for code_a, code_b in INVALID_COMBOS:
        if code_a in present_codes and code_b in present_codes:
            item_a = code_map[code_a][0]["item_id"]
            violations.append({
                "rule_id": "R05_INVALID_COMBO",
                "severity": "HIGH",
                "item_id": item_a,
                "description": (
                    f"Incompatible procedures detected in the same bill: "
                    f"'{code_a}' and '{code_b}' are not typically billed together."
                ),
            })

    # --- Rule R06: Unknown Category with Significant Charge ---
    for item in items:
        if (item["mapped_category"] == "UNKNOWN"
                and item.get("unit_price") is not None
                and item["unit_price"] > 5000):
            violations.append({
                "rule_id": "R06_UNMAPPED_HIGH_CHARGE",
                "severity": "MEDIUM",
                "item_id": item["item_id"],
                "description": (
                    f"'{item['raw_description']}' could not be categorized and has "
                    f"a significant charge of ₹{item['unit_price']:,.0f}. "
                    f"Manual review required."
                ),
            })

    return violations
