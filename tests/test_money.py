from __future__ import annotations

from decimal import Decimal

import pytest

from qriskit._money import format_amount, format_percent, parse_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (25000, "25000"),
        ("25000", "25000"),
        (" 25000 ", "25000"),
        (Decimal("25000"), "25000"),
        (Decimal("25000.00"), "25000"),
        ("15000.5", "15000.50"),
        ("15000.50", "15000.50"),
        (Decimal("23.72"), "23.72"),
        (Decimal("1E+2"), "100"),
        ("9999999999999", "9999999999999"),
        ("9999999999.99", "9999999999.99"),
    ],
)
def test_format_amount(value: object, expected: str) -> None:
    assert format_amount(value) == expected


@pytest.mark.parametrize("value", [0.1, 25000.0, True, None, [1]])
def test_format_amount_rejects_wrong_types(value: object) -> None:
    with pytest.raises(TypeError):
        format_amount(value)


def test_float_error_explains_why() -> None:
    with pytest.raises(TypeError, match="floats are imprecise"):
        format_amount(0.1)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (0, "greater than 0"),
        (-5, "greater than 0"),
        ("-5", "not a plain positive number"),
        ("1e3", "not a plain positive number"),
        ("1,000", "not a plain positive number"),
        ("", "not a plain positive number"),
        ("10.123", "not a plain positive number"),
        (Decimal("10.123"), "more than 2 decimals"),
        (Decimal("NaN"), "finite"),
        (Decimal("Infinity"), "finite"),
        (10**13, "longer than 13"),
        ("99999999999.99", "longer than 13"),
        (Decimal("1E+40"), "longer than 13"),
    ],
)
def test_format_amount_rejects_bad_values(value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        format_amount(value)


def test_format_percent() -> None:
    assert format_percent("2.5") == "2.50"
    assert format_percent(10) == "10"
    assert format_percent("99.99") == "99.99"


@pytest.mark.parametrize("value", ["100", "99.999", 0])
def test_format_percent_rejects(value: object) -> None:
    with pytest.raises(ValueError):
        format_percent(value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("25000", Decimal("25000")),
        ("23.72", Decimal("23.72")),
        (None, None),
        ("0", None),
        ("abc", None),
        ("-1", None),
        ("1.234", None),
    ],
)
def test_parse_decimal(text: str | None, expected: Decimal | None) -> None:
    assert parse_decimal(text) == expected
