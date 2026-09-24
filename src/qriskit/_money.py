"""Money parsing and formatting. Floats are rejected on purpose."""

from __future__ import annotations

import re
from decimal import Decimal

_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")
_CENT = Decimal("0.01")
MAX_PERCENT = Decimal("99.99")


def _to_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        hint = "; floats are imprecise for money" if isinstance(value, float) else ""
        raise TypeError(f"{field} must be int, str or Decimal, not {type(value).__name__}{hint}")
    if isinstance(value, str):
        text = value.strip()
        if not _NUMBER.fullmatch(text):
            raise ValueError(
                f"{field} {value!r} is not a plain positive number with at most 2 decimals"
            )
        return Decimal(text)
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError(f"{field} must be a finite number, got {value!r}")
    return number


def format_decimal(
    value: object, *, field: str, max_len: int, maximum: Decimal | None = None
) -> str:
    """Validate ``value`` and format it for a QRIS amount field.

    Whole numbers have no decimals (``25000``); others have two (``15000.50``).
    """
    number = _to_decimal(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be greater than 0, got {value!r}")
    if number.adjusted() + 1 > max_len:
        raise ValueError(f"{field} {value!r} is longer than {max_len} characters")
    if number != number.quantize(_CENT):
        raise ValueError(f"{field} {value!r} has more than 2 decimals")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} must be at most {maximum}, got {value!r}")
    number = number.quantize(_CENT)
    text = str(int(number)) if number == number.to_integral_value() else f"{number:f}"
    if len(text) > max_len:
        raise ValueError(f"{field} {text} is longer than {max_len} characters")
    return text


def format_amount(value: object, *, field: str = "amount") -> str:
    return format_decimal(value, field=field, max_len=13)


def format_percent(value: object) -> str:
    return format_decimal(value, field="percentage", max_len=5, maximum=MAX_PERCENT)


def parse_decimal(text: str | None) -> Decimal | None:
    """Read an amount written in a payload; ``None`` if missing or malformed."""
    if text is None or not _NUMBER.fullmatch(text):
        return None
    number = Decimal(text)
    return number if number > 0 else None
