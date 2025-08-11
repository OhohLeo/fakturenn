import re
from typing import Dict, Optional
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


def extract_month_from_invoice_date(date_label: str) -> str:
    """Return a month label (French) extracted from a human date string.

    Strategies:
    - If a French month name appears in the label, return it capitalized as in canonical map
    - Else if we detect numeric formats like YYYY-MM, YYYY/MM, MM/YYYY, map to French name
    - Else return the original label (last resort)
    """
    if not date_label:
        return ""

    lower = date_label.lower()
    for name_lower, canonical in FRENCH_MONTH_NAMES.items():
        if name_lower in lower:
            return canonical

    # Try numeric patterns
    m = re.search(r"(?P<y>\d{4})[-/](?P<m>\d{2})", date_label)
    if m:
        num = m.group("m")
        return FRENCH_MONTHS.get(num, date_label)

    m = re.search(r"(?P<m>\d{2})[-/](?P<y>\d{4})", date_label)
    if m:
        num = m.group("m")
        return FRENCH_MONTHS.get(num, date_label)

    return date_label


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
