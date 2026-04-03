"""
Layer 2 — Processing & Normalization
Validates schema, applies regex parsing, maps to category via lookup table,
handles missing values, and produces canonical LineItem records.
"""
import re
import uuid
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lookup: map raw procedure keywords → internal category + procedure_code
# ---------------------------------------------------------------------------
CATEGORY_LOOKUP = [
    {"keywords": ["mri", "magnetic resonance", "nuclear magnetic"], "category": "RADIOLOGY", "code": "RAD_MRI"},
    {"keywords": ["ct scan", "computed tomography", "ct chest", "ct abdomen", "hrct"], "category": "RADIOLOGY", "code": "RAD_CT"},
    {"keywords": ["x-ray", "xray", "radiograph", "fluoroscopy"], "category": "RADIOLOGY", "code": "RAD_XRAY"},
    {"keywords": ["ultrasound", "usg", "sonography", "doppler"], "category": "RADIOLOGY", "code": "RAD_USG"},
    {"keywords": ["ecg", "electrocardiogram", "ekg"], "category": "CARDIOLOGY", "code": "CARD_ECG"},
    {"keywords": ["echocardiogram", "echo"], "category": "CARDIOLOGY", "code": "CARD_ECHO"},
    {"keywords": ["blood test", "cbc", "complete blood count", "haemogram", "hemogram", "wbc", "rbc"], "category": "PATHOLOGY", "code": "PATH_CBC"},
    {"keywords": ["urine test", "urine analysis", "urine culture", "urinalysis"], "category": "PATHOLOGY", "code": "PATH_URINE"},
    {"keywords": ["lipid profile", "cholesterol", "triglycerides"], "category": "PATHOLOGY", "code": "PATH_LIPID"},
    {"keywords": ["blood sugar", "glucose", "hba1c"], "category": "PATHOLOGY", "code": "PATH_GLUCOSE"},
    {"keywords": ["icu", "intensive care", "critical care", "nicu", "picu"], "category": "ICU", "code": "ICU_DAY"},
    {"keywords": ["room charge", "ward charge", "bed charge", "accommodation", "room rent", "stay", "admission fee"], "category": "ROOM", "code": "ROOM_DAY"},
    {"keywords": ["nursing charge", "nursing care", "nurse fee"], "category": "NURSING", "code": "NURS_DAY"},
    {"keywords": ["oxygen", "o2 charge", "ventilator", "respirator"], "category": "CONSUMABLE", "code": "CON_O2"},
    {"keywords": ["operation", "surgery", "surgical", "procedure charge", "ot charge", "implant", "stent", "pacemaker", "incision", "excision"], "category": "SURGERY", "code": "SURG_GEN"},
    {"keywords": ["anaesthesia", "anesthesia", "anaesthetic", "epidural"], "category": "ANAESTHESIA", "code": "ANAES_GEN"},
    {"keywords": ["doctor visit", "consultation", "doctor fee", "physician fee", "specialist fee", "visiting charge", "surgeon fee"], "category": "CONSULTATION", "code": "CONS_DOC"},
    {"keywords": ["tablet", "capsule", "syrup", "injection", "medicine", "drug", "pharmacy", "iv fluid", "paracetamol", "antibiotic", "cream", "ointment", "painkiller", "drops", "lotion", "gel", "powder", "vaccine", "inhaler", "suppository", "dose", "mg", "ml"], "category": "PHARMACY", "code": "PHARM_GEN"},
    {"keywords": ["dressing", "wound care", "bandage", "syringe", "gloves", "mask", "cotton", "gauze", "catheter", "cannula", "needle", "swab", "tape", "kit"], "category": "CONSUMABLE", "code": "CON_DRESS"},
    {"keywords": ["ambulance", "transport"], "category": "TRANSPORT", "code": "TRANS_AMB"},
    {"keywords": ["physiotherapy", "physio", "rehabilitation", "therapy"], "category": "THERAPY", "code": "THERAPY_PHYSIO"},
]

PRICE_PATTERN = re.compile(r"[\u20b9$]?\s*(\d[\d,]*(?:\.\d{1,2})?)")
QTY_PATTERN = re.compile(r"(\d+)\s*(?:days?|nos?|units?|doses?|times?|sessions?)", re.I)

# Patterns for post-filtering NLP-extracted items
_PURE_NUMERIC = re.compile(r"^[\d\s,.\-/]+$")
_SPECIAL_CHARS_ONLY = re.compile(r"^[^a-zA-Z]*$")


def _post_filter_nlp_items(items: list[dict]) -> list[dict]:
    """
    Post-filter to remove garbage items that slipped through the NLP parser.
    Applied only to NLP-parsed (OCR) bills, not structured JSON.
    """
    filtered = []
    for item in items:
        desc = item.get("raw_description", "").strip()
        price = item.get("unit_price")
        category = item.get("mapped_category", "UNKNOWN")

        # Skip purely numeric descriptions
        if _PURE_NUMERIC.match(desc):
            continue

        # Skip descriptions with no alphabetic characters
        if _SPECIAL_CHARS_ONLY.match(desc):
            continue

        # Skip single-character descriptions
        if len(desc) <= 1:
            continue

        # Skip UNKNOWN items with absurdly low prices (OCR noise)
        if category == "UNKNOWN" and price is not None and price < 10:
            continue

        # Skip descriptions that are just punctuation/symbols
        alpha_count = sum(1 for c in desc if c.isalpha())
        if alpha_count < 2:
            continue

        filtered.append(item)

    return filtered


def _map_category(raw_desc: str) -> dict:
    desc_lower = raw_desc.lower()
    for entry in CATEGORY_LOOKUP:
        if any(kw in desc_lower for kw in entry["keywords"]):
            return {"category": entry["category"], "code": entry["code"]}
    return {"category": "UNKNOWN", "code": "UNKNOWN"}


def _extract_price(text: str) -> float | None:
    m = PRICE_PATTERN.search(text)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _extract_qty(text: str) -> float:
    m = QTY_PATTERN.search(text)
    if m:
        return float(m.group(1))
    return 1.0


def normalize_bill(raw_payload: str) -> dict[str, Any]:
    """
    Accepts raw bill payload (JSON string OR OCR raw text). 
    Returns canonical bill dict with line_items[].
    Handles missing values with flags.
    """
    errors = []
    flags_global = []

    # Check if payload is JSON or raw OCR text
    is_json = True
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        is_json = False
        data = {}

    canonical_items = []
    
    if is_json:
        # Required field validation for JSON
        required = ["patient_id", "hospital_name", "line_items"]
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        if errors:
            return {"ok": False, "error": "; ".join(errors), "line_items": []}

        # Process structured JSON items
        for idx, raw_item in enumerate(data.get("line_items", [])):
            item_id = str(uuid.uuid4())
            quality_flags = []

            raw_desc = str(raw_item.get("description") or raw_item.get("name") or f"item_{idx}").strip()
            mapped = _map_category(raw_desc)

            # Unit price
            unit_price = raw_item.get("unit_price") or raw_item.get("price") or raw_item.get("amount")
            if unit_price is None:
                unit_price = _extract_price(raw_desc)
                if unit_price:
                    quality_flags.append("PRICE_FROM_DESC")
                else:
                    quality_flags.append("PRICE_MISSING")

            try:
                unit_price = float(unit_price) if unit_price is not None else None
            except (ValueError, TypeError):
                unit_price = None
                quality_flags.append("PRICE_UNPARSEABLE")

            # Quantity
            quantity = raw_item.get("quantity") or raw_item.get("qty") or raw_item.get("days")
            if quantity is None:
                quantity = _extract_qty(raw_desc)
                quality_flags.append("QTY_INFERRED")
            try:
                quantity = float(quantity)
            except (ValueError, TypeError):
                quantity = 1.0

            # Total price
            total_price = raw_item.get("total") or raw_item.get("total_price") or raw_item.get("amount")
            if total_price is None and unit_price is not None:
                total_price = unit_price * quantity
                quality_flags.append("TOTAL_COMPUTED")
            elif total_price is None:
                quality_flags.append("TOTAL_UNKNOWN")
            try:
                total_price = float(total_price) if total_price is not None else None
            except (ValueError, TypeError):
                total_price = None

            if unit_price is None and total_price is not None and quantity > 0:
                unit_price = total_price / quantity
                quality_flags.append("PRICE_INFERRED")

            date_of_service = raw_item.get("date") or data.get("date_of_service") or data.get("admission_date") or "UNKNOWN"

            canonical_items.append({
                "item_id": item_id,
                "raw_description": raw_desc,
                "mapped_category": mapped["category"],
                "procedure_code": mapped["code"],
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "date_of_service": date_of_service,
                "data_quality_flags": quality_flags,
            })
    else:
        # Route to NLP Parser if Payload is Unstructured OCR Text
        from layers.nlp_parser import parse_unstructured_text
        flags_global.append("NLP_PARSED")
        # In this workflow, patient_id / hospital_name are extracted differently or injected earlier
        parsed_items = parse_unstructured_text(raw_payload, CATEGORY_LOOKUP)
        # Post-filter: remove garbage items that are clearly metadata/noise
        parsed_items = _post_filter_nlp_items(parsed_items)
        for p_item in parsed_items:
            p_item["item_id"] = str(uuid.uuid4())
            canonical_items.append(p_item)

    return {
        "ok": True,
        "patient_id": data.get("patient_id", "UNKNOWN"),
        "hospital_name": data.get("hospital_name", "UNKNOWN"),
        "date_of_service": data.get("date_of_service", "UNKNOWN"),
        "line_items": canonical_items,
        "global_flags": flags_global,
    }
