"""
Layer 2 Supplement — NLP Parser
Extracts line items from unstructured OCR text blocks using heuristics and fuzzy matching,
bypassing the need for complex, heavy deep learning models.

Includes robust metadata filtering to avoid treating phone numbers, GST numbers,
addresses, dates, and other non-medical text as billable line items.
"""
import re
from thefuzz import process, fuzz

# Pattern for detecting a line containing a reasonable price at the end
# Very resilient to missing commas (4000 instead of 4,000) and trailing OCR table-border noise (| or -)
PRICE_LINE_PATTERN = re.compile(r"^(.*?)(?:rs\.?|inr|\u20b9|\$)?\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*[^\w]*$", re.IGNORECASE)

# ── Metadata / Noise Filters ──────────────────────────────────────────────────
# These patterns identify lines that are clearly NOT medical procedures

# GST Number: 2-digit state code + 5 alpha + 4 digits + 1 alpha + 1 digit + 1 alphanumeric + 1 checksum
GST_PATTERN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}", re.IGNORECASE)

# Phone numbers: 7+ consecutive digits (with optional separators)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s\-]{7,})")

# PIN code: standalone 6-digit number (Indian postal codes)
PINCODE_PATTERN = re.compile(r"\b\d{6}\b")

# Date patterns: "Dec 2024", "13-Dec-2024", "Jan 2", "Jul 2025", "12/03/2024", etc.
DATE_PATTERN = re.compile(
    r"(?:"
    r"\b\d{1,2}[-/]\w{3,9}[-/]?\d{0,4}\b|"   # 13-Dec-2024, 13/Dec/24
    r"\b\w{3,9}\s+\d{1,4}\b|"                  # Dec 2024, Jan 2
    r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"       # 12/03/2024, 01-01-24
    r")",
    re.IGNORECASE
)

# Address indicators: state names, city names, "India", pincode context
ADDRESS_KEYWORDS = [
    "maharashtra", "karnataka", "tamil nadu", "tamilnadu", "andhra", "telangana",
    "kerala", "gujarat", "rajasthan", "delhi", "mumbai", "pune", "bangalore",
    "bengaluru", "chennai", "hyderabad", "kolkata", "lucknow", "jaipur",
    "india", "road", "street", "lane", "nagar", "colony", "sector",
    "floor", "building", "tower", "block", "plot", "flat", "apartment",
    "dist", "district", "taluka", "village", "post office", "p.o.",
    "state", "city", "country", "pin code", "pincode", "zip",
]

# Invoice/receipt/ID keywords
INVOICE_KEYWORDS = [
    "invoice", "receipt", "bill no", "bill number", "ref no", "reference",
    "registration", "uhid", "mr no", "ip no", "op no", "patient id",
    "admission", "discharge", "tin no", "pan no", "gstin", "gst no",
    "cin", "dlno", "dl no", "license", "email", "phone", "tel",
    "fax", "website", "www", "http", ".com", ".in", ".org",
]

# Lines that are purely structural/header content
STRUCTURAL_KEYWORDS = [
    "terms and conditions", "thank you", "get well soon", "total amount",
    "grand total", "subtotal", "sub total", "net amount", "cgst", "sgst",
    "igst", "tax", "discount", "advance", "balance", "paid", "due",
    "amount in words", "rupees", "authorized signatory", "signature",
    "printed on", "page", "hospital", "clinic", "nursing home",
    "name of patient", "patient name", "age", "sex", "gender",
    "ward no", "bed no", "room no", "doctor name", "dr.",
    "date of admission", "date of discharge", "doa", "dod",
    "date:",  # catches "Date: Dec 2024" style lines
]


def _is_metadata_line(line: str) -> bool:
    """Returns True if the line is clearly metadata/noise, not a medical line item."""
    line_lower = line.lower().strip()

    # Skip very short lines
    if len(line_lower) < 4:
        return True

    # GST number
    if GST_PATTERN.search(line):
        return True

    # Phone number (7+ digits in sequence)
    digits_only = re.sub(r'\D', '', line)
    if len(digits_only) >= 7 and len(re.findall(r'[a-zA-Z]', line)) < 3:
        return True

    # Address line
    if any(kw in line_lower for kw in ADDRESS_KEYWORDS):
        return True

    # Invoice/ID line
    if any(kw in line_lower for kw in INVOICE_KEYWORDS):
        return True

    # Structural/header content
    if any(kw in line_lower for kw in STRUCTURAL_KEYWORDS):
        return True

    # Line is mostly digits/punctuation with very few alphabetic chars
    alpha_chars = len(re.findall(r'[a-zA-Z]', line))
    if alpha_chars < 3:
        return True

    # Standalone PIN code (6 consecutive digits)
    if PINCODE_PATTERN.search(line) and alpha_chars < 5:
        return True

    return False


def _is_valid_item(raw_desc: str, unit_price: float) -> bool:
    """Additional validation after regex extraction — sanity check the parsed item."""
    # Description must have at least 3 alphabetic characters
    alpha_chars = len(re.findall(r'[a-zA-Z]', raw_desc))
    if alpha_chars < 3:
        return False

    desc_stripped = raw_desc.strip()
    
    # Reject if description is just a date fragment
    if DATE_PATTERN.fullmatch(desc_stripped):
        return False
        
    # Reject if description contains clear date tokens like months alongside numbers
    if re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2,4}\b', desc_stripped, re.IGNORECASE):
        return False

    # Reject extremely low prices (likely OCR noise) UNLESS it is exactly 0 
    # (which implies the price was stripped or will be filled later, but the item string is real).
    if 0 < unit_price < 5:
        return False

    # Reject descriptions with a high ratio of numbers (like HSN codes, phone numbers, mixed OCR bits)
    # Even if they have spaces! OCR tabular output frequently breaks.
    digit_ratio = len(re.findall(r'\d', desc_stripped)) / max(1, len(desc_stripped))
    if digit_ratio > 0.4:
        return False

    # Reject single special characters or punctuation-only descriptions
    if len(re.sub(r'[^a-zA-Z]', '', desc_stripped)) < 2:
        return False

    return True


def parse_unstructured_text(raw_text: str, categories_lookup: list[dict]) -> list[dict]:
    """
    Takes a raw OCR text dump and tries to extract line item dicts.
    Returns format matches canonical line_item structure.

    Applies robust filtering to exclude metadata, addresses, phone numbers, etc.
    """
    line_items = []

    # Pre-compute lexicon dictionary for fuzzy matching
    lexicon = {}
    for entry in categories_lookup:
        for kw in entry["keywords"]:
            lexicon[kw] = {"category": entry["category"], "code": entry["code"]}

    lexicon_keys = list(lexicon.keys())

    # Line by line heuristic parsing
    lines = raw_text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) < 5:
            continue

        # ── FILTER 1: Skip metadata lines before attempting price extraction ──
        if _is_metadata_line(line):
            continue

        # Check if the line looks like a bill item (has a price at the end)
        match = PRICE_LINE_PATTERN.search(line)
        
        raw_desc = ""
        unit_price = 0.0
        
        if match:
            raw_desc = match.group(1).strip()
            raw_desc = re.sub(r'[\.\-\:]+$', '', raw_desc).strip()

            raw_price = match.group(2).replace(',', '')
            try:
                unit_price = float(raw_price)
            except ValueError:
                unit_price = 0.0
        else:
            # Maybe the price was stripped by OCR column-breaking? 
            # Treat the whole line as description and price as 0
            raw_desc = line
            unit_price = 0.0

        if not raw_desc:
            continue

        # ── FILTER 2: Validate the extracted item ────────────────────────
        if not _is_valid_item(raw_desc, unit_price):
            continue

        # Category Matching: try substring first (more reliable), then fuzzy
        mapped_category = "UNKNOWN"
        code = "UNKNOWN"
        flags = ["EXTRACTED_VIA_NLP"]
        if unit_price == 0:
            flags.append("PRICE_MISSING_OCR")

        desc_lower = raw_desc.lower()
        # Substring-based matching (same as normalization.py's _map_category)
        matched_via_substring = False
        for entry in categories_lookup:
            if any(kw in desc_lower for kw in entry["keywords"]):
                mapped_category = entry["category"]
                code = entry["code"]
                matched_via_substring = True
                break

        # Fuzzy matching fallback
        if not matched_via_substring and lexicon_keys:
            best_match, score = process.extractOne(desc_lower, lexicon_keys, scorer=fuzz.token_sort_ratio)
            if score > 60:
                mapped_category = lexicon[best_match]["category"]
                code = lexicon[best_match]["code"]
            else:
                flags.append("NLP_LOW_CONFIDENCE_MAPPING")

        # If it has NO price AND we couldn't confidently map it to a category, it's just OCR noise (drop it)
        if unit_price == 0 and mapped_category == "UNKNOWN":
            continue

        line_items.append({
            "raw_description": raw_desc,
            "mapped_category": mapped_category,
            "procedure_code": code,
            "quantity": 1.0,
            "unit_price": unit_price,
            "total_price": unit_price,
            "date_of_service": "UNKNOWN",
            "data_quality_flags": flags
        })

    return line_items
