"""Bugs found in other QRIS tools (see ``Riset/Pelajaran dari qris-dinamis``)."""

from __future__ import annotations

from decimal import Decimal

import pytest

import qris
from helpers import STATIC, payload, static_pairs
from qris import QRISParseError, Tip


@pytest.mark.parametrize("name", ["TOKO 5802ID", "WARUNG 6304ABCD", "KEDAI 010211", "5412345"])
def test_values_that_look_like_tags(name: str) -> None:
    """B4/#12: string search for "58" or "6304" corrupted payloads."""
    text = payload(*static_pairs(t59=name))
    q = qris.parse(text)
    assert q.merchant_name == name
    d = q.to_dynamic(10000)
    assert d.merchant_name == name
    assert d.amount == Decimal("10000")
    assert qris.validate(d) == []


@pytest.mark.parametrize("name", ["KOPI SÜSU", "咖啡店", "WARUNG 😀"])
def test_non_ascii_names(name: str) -> None:
    """B1/#6: CRC must use UTF-8 bytes and lengths must count characters."""
    text = payload(*static_pairs(t59=name))
    assert qris.validate(text) == []
    d = qris.parse(text).to_dynamic(5000)
    assert qris.validate(d) == []
    assert d.merchant_name == name


def test_truncated_payload_raises() -> None:
    """B2: a cut-off payload must not be read partially."""
    with pytest.raises(QRISParseError):
        qris.parse(STATIC[:50])


def test_malformed_template_survives_conversion() -> None:
    """B3: rebuilding templates from partial parses lost data."""
    text = payload(*static_pairs(t62="07XX"))
    d = qris.parse(text).to_dynamic(1000)
    assert d.get("62") == "07XX"


def test_amount_inserted_without_tag_58() -> None:
    """B4: amount was only inserted when tag 58 was found."""
    d = qris.parse(payload(*static_pairs(t58=None))).to_dynamic(1000)
    assert d.amount == Decimal("1000")


def test_fee_indicator_codes() -> None:
    """#12: fixed fee is 02 and percentage fee is 03."""
    q = qris.parse(STATIC)
    assert q.to_dynamic(1000, tip=Tip.fixed(100)).get("55") == "02"
    assert q.to_dynamic(1000, tip=Tip.percent(1)).get("55") == "03"
    assert q.to_dynamic(1000, tip=Tip.prompt()).get("55") == "01"


def test_pasted_payload_with_newline() -> None:
    """#6: copy-paste adds whitespace."""
    assert qris.is_valid(STATIC + "\n")
    assert qris.is_valid("\t" + STATIC + " \r\n")


def test_missing_point_of_initiation_is_not_static() -> None:
    """B9: a missing tag 01 was silently treated as static."""
    q = qris.parse(payload(*static_pairs(t01=None)))
    assert q.point_of_initiation is None
    assert "tag.required" in [i.code for i in qris.validate(q)]


def test_pan_and_merchant_id_are_separate() -> None:
    """B8: PAN and merchant ID were merged into one field."""
    account = qris.parse(STATIC).merchant_accounts[0]
    assert account.pan == "9360091412345678901"
    assert account.merchant_id == "G123456789"
