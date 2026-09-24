"""QRIS tag rules: names, formats, lengths and which tags hold nested templates.

Sources: EMVCo QR Code Specification for Payment Systems (Merchant-Presented Mode)
and QRIS practice. See ``Referensi/Struktur Payload QRIS`` in the design notes.
"""

from __future__ import annotations

from dataclasses import dataclass

TAG_PFI = "00"
TAG_POI = "01"
TAG_NATIONAL = "51"
TAG_MCC = "52"
TAG_CURRENCY = "53"
TAG_AMOUNT = "54"
TAG_TIP = "55"
TAG_FEE_FIXED = "56"
TAG_FEE_PERCENT = "57"
TAG_COUNTRY = "58"
TAG_NAME = "59"
TAG_CITY = "60"
TAG_POSTAL = "61"
TAG_ADDITIONAL = "62"
TAG_CRC = "63"
TAG_LANGUAGE = "64"

POI_STATIC = "11"
POI_DYNAMIC = "12"
TIP_PROMPT = "01"
TIP_FIXED = "02"
TIP_PERCENT = "03"
NATIONAL_GUID = "ID.CO.QRIS.WWW"
CURRENCY_IDR = "360"
COUNTRY_ID = "ID"
SUB_REFERENCE = "05"

REQUIRED_ROOT_TAGS = (TAG_POI, TAG_MCC, TAG_CURRENCY, TAG_COUNTRY, TAG_NAME, TAG_CITY)
TRANSACTION_TAGS = frozenset({TAG_AMOUNT, TAG_TIP, TAG_FEE_FIXED, TAG_FEE_PERCENT})


@dataclass(frozen=True)
class TagRule:
    name: str
    numeric: bool
    max_len: int
    exact: bool = False


ROOT_RULES: dict[str, TagRule] = {
    TAG_PFI: TagRule("Payload Format Indicator", True, 2, exact=True),
    TAG_POI: TagRule("Point of Initiation Method", True, 2, exact=True),
    TAG_MCC: TagRule("Merchant Category Code", True, 4, exact=True),
    TAG_CURRENCY: TagRule("Transaction Currency", True, 3, exact=True),
    TAG_AMOUNT: TagRule("Transaction Amount", False, 13),
    TAG_TIP: TagRule("Tip or Convenience Indicator", True, 2, exact=True),
    TAG_FEE_FIXED: TagRule("Value of Convenience Fee Fixed", False, 13),
    TAG_FEE_PERCENT: TagRule("Value of Convenience Fee Percentage", False, 5),
    TAG_COUNTRY: TagRule("Country Code", False, 2, exact=True),
    TAG_NAME: TagRule("Merchant Name", False, 25),
    TAG_CITY: TagRule("Merchant City", False, 15),
    TAG_POSTAL: TagRule("Postal Code", False, 10),
    TAG_ADDITIONAL: TagRule("Additional Data Field Template", False, 99),
    TAG_CRC: TagRule("CRC", False, 4, exact=True),
    TAG_LANGUAGE: TagRule("Merchant Information - Language Template", False, 99),
}

# Root tags checked by the generic format/length rule. The others have
# dedicated checks with more specific issue codes.
GENERIC_ROOT_TAGS = frozenset({TAG_MCC, TAG_NAME, TAG_CITY, TAG_POSTAL})

MERCHANT_ACCOUNT_RULES: dict[str, TagRule] = {
    "00": TagRule("Globally Unique Identifier", False, 32),
    "01": TagRule("Merchant PAN", True, 19),
    "02": TagRule("Merchant ID", False, 15),
    "03": TagRule("Merchant Criteria", False, 3, exact=True),
}

ADDITIONAL_DATA_RULES: dict[str, TagRule] = {
    "01": TagRule("Bill Number", False, 25),
    "02": TagRule("Mobile Number", False, 25),
    "03": TagRule("Store Label", False, 25),
    "04": TagRule("Loyalty Number", False, 25),
    "05": TagRule("Reference Label", False, 25),
    "06": TagRule("Customer Label", False, 25),
    "07": TagRule("Terminal Label", False, 25),
    "08": TagRule("Purpose of Transaction", False, 25),
    "09": TagRule("Additional Consumer Data Request", False, 3),
    "10": TagRule("Merchant Tax ID", False, 20),
    "11": TagRule("Merchant Channel", False, 3, exact=True),
}

LANGUAGE_RULES: dict[str, TagRule] = {
    "00": TagRule("Language Preference", False, 2, exact=True),
    "01": TagRule("Merchant Name - Alternate Language", False, 25),
    "02": TagRule("Merchant City - Alternate Language", False, 15),
}


def is_merchant_account(tag: str) -> bool:
    """Tags 02-51 carry merchant account information."""
    return "02" <= tag <= "51"


def is_merchant_account_template(tag: str) -> bool:
    """Tags 26-51 are merchant account templates (nested TLV)."""
    return "26" <= tag <= "51"


def is_template(tag: str) -> bool:
    """True if the tag's value is nested TLV."""
    return (
        is_merchant_account_template(tag)
        or tag in (TAG_ADDITIONAL, TAG_LANGUAGE)
        or "80" <= tag <= "99"
    )


def child_rules(tag: str) -> dict[str, TagRule]:
    """Rules for the sub-tags of template ``tag`` (empty if unknown)."""
    if is_merchant_account_template(tag):
        return MERCHANT_ACCOUNT_RULES
    if tag == TAG_ADDITIONAL:
        return ADDITIONAL_DATA_RULES
    if tag == TAG_LANGUAGE:
        return LANGUAGE_RULES
    return {}
