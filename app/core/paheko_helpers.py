import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PahekoMapping:
    type: str
    label_template: str
    debit: str
    credit: str

    def parse(
        self,
    ) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str]]:
        # Parsing placeholder: kept for API compatibility
        return None, None, None, None


def parse_transaction_field(tx_field: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a paheko_transaction like "626:debit" to (account_debit, account_credit)
    - Accepts multiple entries separated by newlines/commas/semicolons.
    - Returns the first debit and the first credit accounts found.
    """
    if not tx_field:
        return None, None

    debit_account: Optional[str] = None
    credit_account: Optional[str] = None

    # Split on newlines, commas, or semicolons
    parts = re.split(r"[\r\n;,]+", tx_field)
    for raw in parts:
        part = raw.strip()
        if not part:
            continue
        m = re.match(r"\s*([0-9A-Za-z]+)\s*:\s*(debit|credit)\s*$", part)
        if not m:
            continue
        account = m.group(1)
        side = m.group(2)
        if side == "debit" and debit_account is None:
            debit_account = account
        elif side == "credit" and credit_account is None:
            credit_account = account
        # Stop early if we have both
        if debit_account and credit_account:
            break

    return debit_account, credit_account


def parse_transaction_fields(
    debit_field: str, credit_field: str
) -> Tuple[List[str], List[str]]:
    """
    Split debit and credit account lists from two separate fields.
    Accepts separators: newlines, commas, semicolons. Returns ordered lists.
    """

    def split_accounts(value: str) -> List[str]:
        if not value:
            return []
        parts = re.split(r"[\r\n;,]+", value)
        return [p.strip() for p in parts if p and p.strip()]

    return split_accounts(debit_field), split_accounts(credit_field)


def build_paheko_lines_if_needed(
    mapping: PahekoMapping, amount_eur: Optional[float]
) -> Dict:
    debit_list, credit_list = parse_transaction_fields(mapping.debit, mapping.credit)
    first_debit = debit_list[0] if debit_list else None
    first_credit = credit_list[0] if credit_list else None
    payload: Dict = {}

    if first_debit and first_credit:
        if amount_eur is not None:
            payload.update(
                {"amount": amount_eur, "debit": first_debit, "credit": first_credit}
            )
    elif first_debit or first_credit:
        if amount_eur is not None:
            payload.update({"amount": amount_eur})
            if first_debit:
                payload["debit"] = first_debit
            if first_credit:
                payload["credit"] = first_credit

    return payload
