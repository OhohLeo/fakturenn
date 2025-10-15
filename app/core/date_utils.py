import re
from typing import Dict, Optional, Tuple
from datetime import datetime, date

FRENCH_MONTHS = {
    "01": "Janvier",
    "02": "Février",
    "03": "Mars",
    "04": "Avril",
    "05": "Mai",
    "06": "Juin",
    "07": "Juillet",
    "08": "Août",
    "09": "Septembre",
    "10": "Octobre",
    "11": "Novembre",
    "12": "Décembre",
}

FRENCH_MONTH_NAMES = {v.lower(): v for v in FRENCH_MONTHS.values()}

# Map lowercased French month name to month number ("01".."12")
FRENCH_MONTH_NAME_TO_NUM: Dict[str, str] = {
    name.lower(): num for num, name in FRENCH_MONTHS.items()
}


def _extract_year_from_text(text: str) -> Optional[int]:
    m = re.search(r"(\d{4})", text)
    if not m:
        return None
    try:
        y = int(m.group(1))
        # Basic sanity check
        if 1900 <= y <= 2100:
            return y
    except Exception:
        return None
    return None


def _has_explicit_month(text: str) -> bool:
    lower = text.lower()
    if any(name_lower in lower for name_lower in FRENCH_MONTH_NAME_TO_NUM.keys()):
        return True
    if re.search(r"(\d{4})[-/](\d{2})", text) or re.search(r"(\d{2})[-/](\d{4})", text):
        return True
    return False


def _get_quarter_from_month(month: int) -> str:
    """Get quarter string from month number (1-12)."""
    if 1 <= month <= 3:
        return "Q1"
    elif 4 <= month <= 6:
        return "Q2"
    elif 7 <= month <= 9:
        return "Q3"
    elif 10 <= month <= 12:
        return "Q4"
    return ""


def extract_month_and_year_from_invoice_date(date_label: str) -> Tuple[str, int, str]:
    """Extract a month label (French), year, and quarter from a human date string.

    Returns a tuple: (month_label, year, quarter). The month_label is a French month name in
    canonical capitalization when a month is explicit, or the original label if the
    input does not contain an explicit month (to preserve previous behavior). The
    returned year is always an integer; when no year can be detected, the current
    year is used as a fallback. Quarter is "Q1", "Q2", "Q3", or "Q4".
    """
    if not date_label:
        # No label means no month info; return empty month and current year fallback
        return "", datetime.now().year, ""

    original = date_label.strip()

    # Try full parsing first
    dt = None
    try:
        dt = parse_date_label_to_date(date_label)
    except Exception:
        dt = None

    if dt:
        if not _has_explicit_month(date_label):
            # Preserve original label as "month" when only a year is present
            y = _extract_year_from_text(date_label) or dt.year
            return original, y, ""
        month_label = FRENCH_MONTHS.get(f"{dt.month:02d}", "")
        quarter = _get_quarter_from_month(dt.month)
        return month_label, dt.year, quarter

    # Fallbacks when we couldn't parse to a date
    lower = date_label.lower()

    # Named French month
    for name_lower, canonical in FRENCH_MONTH_NAMES.items():
        if name_lower in lower:
            y = _extract_year_from_text(date_label) or datetime.now().year
            # Get month number from the month name
            month_num_str = FRENCH_MONTH_NAME_TO_NUM.get(name_lower, "01")
            month_num = int(month_num_str)
            quarter = _get_quarter_from_month(month_num)
            return canonical, y, quarter

    # Numeric formats
    m = re.search(r"(?P<y>\d{4})[-/](?P<m>\d{2})", date_label)
    if m:
        num = m.group("m")
        month_label = FRENCH_MONTHS.get(num, original)
        y = int(m.group("y"))
        month_num = int(num)
        quarter = _get_quarter_from_month(month_num)
        return month_label, y, quarter

    m = re.search(r"(?P<m>\d{2})[-/](?P<y>\d{4})", date_label)
    if m:
        num = m.group("m")
        month_label = FRENCH_MONTHS.get(num, original)
        y = int(m.group("y"))
        month_num = int(num)
        quarter = _get_quarter_from_month(month_num)
        return month_label, y, quarter

    # Last resort: keep original label and choose reasonable year
    y = _extract_year_from_text(date_label) or datetime.now().year
    return original, y, ""


def extract_month_from_invoice_date(date_label: str) -> Tuple[str, Optional[int]]:
    """Backward-compatible wrapper. Prefer extract_month_and_year_from_invoice_date."""
    month_label, year, _ = extract_month_and_year_from_invoice_date(date_label)
    return month_label, year


def parse_date_label_to_date(date_label: str) -> Optional[date]:
    """Parse various invoice date labels to a concrete date.

    Supported patterns:
    - "YYYY-MM-DD" -> that exact date
    - "YYYY-MM" or "YYYY/MM" -> first day of that month
    - "MM/YYYY" -> first day of that month
    - French month name + year, e.g. "Janvier 2025" -> first day of that month
    - Bare year "YYYY" -> January 1st of that year
    """
    if not date_label:
        return None

    txt = date_label.strip()

    # YYYY-MM-DD
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", txt)
    if m:
        try:
            return datetime.strptime(m.group(0).replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            pass

    # YYYY-MM or YYYY/MM
    m = re.search(r"(\d{4})[-/](\d{2})", txt)
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        try:
            return date(y, mm, 1)
        except Exception:
            return None

    # MM/YYYY
    m = re.search(r"(\d{2})[-/](\d{4})", txt)
    if m:
        mm, y = int(m.group(1)), int(m.group(2))
        try:
            return date(y, mm, 1)
        except Exception:
            return None

    # French month name + year (order-insensitive checks)
    year_match = re.search(r"(\d{4})", txt)
    if year_match:
        y = int(year_match.group(1))
        lower = txt.lower()
        for name_lower, mm_str in FRENCH_MONTH_NAME_TO_NUM.items():
            if name_lower in lower:
                try:
                    return date(y, int(mm_str), 1)
                except Exception:
                    return None
        # If only year present
        try:
            return date(y, 1, 1)
        except Exception:
            return None

    return None
