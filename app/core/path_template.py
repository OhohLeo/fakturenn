"""Path template rendering system for organizing exported files."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

TEMPLATE_VARIABLES = {
    "year": "Invoice year (e.g., 2025)",
    "month": "Invoice month (01-12)",
    "month_name": "Month name in French (Janvier, Février, ...)",
    "quarter": "Quarter (Q1, Q2, Q3, Q4)",
    "date": "Full date (YYYY-MM-DD)",
    "invoice_id": "Invoice identifier",
    "source": "Source name",
    "amount": "Invoice amount (EUR)",
}

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


def get_quarter(month: str) -> str:
    """Get quarter from month number.

    Args:
        month: Month number (01-12)

    Returns:
        Quarter string (Q1-Q4)
    """
    month_int = int(month)
    if month_int <= 3:
        return "Q1"
    elif month_int <= 6:
        return "Q2"
    elif month_int <= 9:
        return "Q3"
    else:
        return "Q4"


def render_path_template(template: str, context: Dict[str, Any]) -> str:
    """Render a path template with context variables.

    Args:
        template: Path template with {variable} placeholders
        context: Context dictionary with values:
            - date: YYYY-MM-DD format
            - invoice_id: str
            - source: str
            - amount_eur: float
            - month_name: Optional[str]
            - other: Any additional values

    Returns:
        Rendered path string

    Example:
        >>> context = {
        ...     'date': '2025-01-15',
        ...     'invoice_id': 'INV-001',
        ...     'source': 'Free',
        ...     'amount_eur': 99.99
        ... }
        >>> render_path_template('{year}/{month}/{source}_{invoice_id}.pdf', context)
        '2025/01/Free_INV-001.pdf'
    """
    if not template:
        raise ValueError("Template cannot be empty")

    render_context = dict(context)  # Copy to avoid modifying original

    # Parse date to extract year, month, quarter
    if "date" in render_context:
        date_str = render_context["date"]
        if isinstance(date_str, str) and len(date_str) >= 7:
            # Assume YYYY-MM-DD format
            year, month = date_str[:4], date_str[5:7]
            render_context.setdefault("year", year)
            render_context.setdefault("month", month)
            render_context.setdefault("month_name", FRENCH_MONTHS.get(month, month))
            render_context.setdefault("quarter", get_quarter(month))

    # Add formatted amount
    if "amount_eur" in render_context:
        amount = render_context["amount_eur"]
        if isinstance(amount, (int, float)):
            render_context.setdefault("amount", f"{amount:.2f}")

    # Render template
    try:
        rendered = template.format(**render_context)
        logger.debug(f"Rendered path template: {template} -> {rendered}")
        return rendered
    except KeyError as e:
        missing_var = str(e).strip("'")
        raise ValueError(
            f"Missing template variable '{missing_var}'. "
            f"Available variables: {', '.join(TEMPLATE_VARIABLES.keys())}"
        ) from e


def validate_path_template(template: str) -> tuple[bool, str]:
    """Validate a path template for completeness.

    Args:
        template: Path template to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_path_template("{year}/{month}/{invoice_id}.pdf")
        (True, "")
        >>> validate_path_template("{year}/{invalid_var}.pdf")
        (False, "Unknown variable: invalid_var")
    """
    if not template:
        return False, "Template cannot be empty"

    # Extract variable names from template
    import re

    variables = re.findall(r"\{(\w+)\}", template)

    for var in variables:
        if var not in TEMPLATE_VARIABLES and var not in [
            "date",
            "amount_eur",
            "source",
            "filename",
        ]:
            return False, f"Unknown variable: {var}"

    # Check for required variables
    if not variables:
        return False, "Template must contain at least one variable"

    return True, ""


def get_template_examples() -> Dict[str, str]:
    """Get example path templates.

    Returns:
        Dictionary of template name -> template string
    """
    return {
        "By Year": "{year}/{filename}",
        "By Year and Month": "{year}/{month}/{filename}",
        "By Year and Quarter": "{year}/Q{quarter}/{filename}",
        "With Source": "{year}/{month}/{source}_{invoice_id}.pdf",
        "With Date": "{year}/{month_name}/{date}_{invoice_id}.pdf",
        "Detailed": "{year}/{month_name}/[{source}] {invoice_id}.pdf",
    }
