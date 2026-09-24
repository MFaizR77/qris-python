from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

import qris
from helpers import EMVCO_SAMPLE, STATIC, payload, static_pairs
from qris import AdditionalData, MerchantAccount, Tip
from qris.errors import QRISParseError


def test_roundtrip_is_exact() -> None:
    assert qris.parse(STATIC).dumps() == STATIC
    assert qris.parse(EMVCO_SAMPLE).dumps() == EMVCO_SAMPLE


def test_str_and_repr() -> None:
    q = qris.parse(STATIC)
    assert str(q) == STATIC
    assert repr(q) == f"QRIS({STATIC!r})"


def test_fields_of_static_sample() -> None:
    q = qris.parse(STATIC)
    assert q.version == "01"
    assert q.point_of_initiation == "static"
    assert q.is_static and not q.is_dynamic
    assert q.mcc == "5812"
    assert q.currency == "360"
    assert q.country == "ID"
    assert q.merchant_name == "TOKO CONTOH"
    assert q.merchant_city == "JAKARTA"
    assert q.postal_code == "10110"
    assert q.amount is None
    assert q.tip is None
    assert q.nmid == "ID1020012345678"
    assert q.crc == "3ACC"
    assert q.additional_data.terminal_label == "KASIR-01"


def test_merchant_accounts() -> None:
    gopay, national = qris.parse(STATIC).merchant_accounts
    assert gopay.tag == "26"
    assert gopay.guid == "COM.GO-JEK.WWW"
    assert gopay.pan == "9360091412345678901"
    assert gopay.merchant_id == "G123456789"
    assert gopay.criteria == "UMI"
    assert gopay.nns == "93600914"
    assert gopay.acquirer is not None and gopay.acquirer.name == "GoPay"
    assert not gopay.is_national
    assert national.is_national
    assert national.merchant_id == "ID1020012345678"


def test_nns_needs_eight_digits() -> None:
    assert MerchantAccount("26", (qris.Node("01", "9360"),)).nns is None
    assert MerchantAccount("26", (qris.Node("01", "93600X14123"),)).nns is None
    assert MerchantAccount("26").acquirer is None


def test_get_paths() -> None:
    q = qris.parse(STATIC)
    assert q.get("59") == "TOKO CONTOH"
    assert q.get("62.07") == "KASIR-01"
    assert q.get("26.00") == "COM.GO-JEK.WWW"
    assert q.get("62.99") is None
    assert q.get("54") is None
    assert q.get("54.01") is None


def test_malformed_template_does_not_break_properties() -> None:
    q = qris.parse(payload(*static_pairs(t62="07XX")))
    assert q.additional_data == AdditionalData()
    assert q.get("62.07") is None
    assert q.get("62") == "07XX"


def test_missing_tags_are_none() -> None:
    q = qris.parse(payload(("00", "01")))
    assert q.point_of_initiation is None
    assert q.merchant_accounts == ()
    assert q.national is None and q.nmid is None
    assert q.additional_data.reference_label is None


def test_amount_and_tips() -> None:
    q = qris.parse(payload(*static_pairs(t01="12"), ("54", "23.72"), ("55", "02"), ("56", "500")))
    assert q.amount == Decimal("23.72")
    assert q.tip == Tip("fixed", Decimal("500"))
    q = qris.parse(payload(("55", "03"), ("57", "2.5")))
    assert q.tip == Tip("percent", Decimal("2.5"))
    assert qris.parse(payload(("55", "01"))).tip == Tip.prompt()
    assert qris.parse(payload(("55", "02"))).tip is None
    assert qris.parse(payload(("55", "03"), ("57", "150"))).tip is None
    assert qris.parse(payload(("55", "09"))).tip is None
    assert qris.parse(payload(("54", "abc"))).amount is None


def test_immutable() -> None:
    q = qris.parse(STATIC)
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.nodes = ()  # type: ignore[misc]


def test_to_dict_is_json_serialisable() -> None:
    data = json.loads(json.dumps(qris.parse(STATIC).to_dict()))
    assert data["merchant_name"] == "TOKO CONTOH"
    assert data["point_of_initiation"] == "static"
    assert data["amount"] is None and data["tip"] is None
    assert data["nmid"] == "ID1020012345678"
    assert data["merchant_accounts"][0]["acquirer"] == "GoPay"
    assert data["merchant_accounts"][1]["acquirer"] is None
    assert data["additional_data"] == {"terminal_label": "KASIR-01"}
    assert data["payload"] == STATIC
    assert data["crc"] == "3ACC"


def test_additional_data_fields() -> None:
    subs = [f"{n:02d}" for n in range(1, 12)]
    value = "".join(f"{sub}02{sub}" for sub in subs) + "5002ZZ"
    data = qris.parse(payload(("62", value))).additional_data
    assert data.bill_number == "01"
    assert data.mobile_number == "02"
    assert data.store_label == "03"
    assert data.loyalty_number == "04"
    assert data.reference_label == "05"
    assert data.customer_label == "06"
    assert data.terminal_label == "07"
    assert data.purpose == "08"
    assert data.consumer_data_request == "09"
    assert data.merchant_tax_id == "10"
    assert data.merchant_channel == "11"
    assert data.to_dict()["50"] == "ZZ"


def test_tip_constructors_validate() -> None:
    assert Tip.fixed("1000").value == Decimal("1000")
    assert Tip.percent(3).value == Decimal("3")
    with pytest.raises(ValueError):
        Tip("fixed")
    with pytest.raises(ValueError):
        Tip("prompt", Decimal(1))
    with pytest.raises(ValueError):
        Tip("other", Decimal(1))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Tip.fixed(1.5)  # type: ignore[arg-type]


def test_merchant_account_create_validates_tag() -> None:
    with pytest.raises(ValueError, match="between 26 and 51"):
        MerchantAccount.create(tag="25", guid="X")


def test_parse_strips_whitespace_and_bom() -> None:
    assert qris.parse(chr(0xFEFF) + f"  {STATIC}\r\n").dumps() == STATIC


def test_parse_errors() -> None:
    with pytest.raises(QRISParseError, match="empty"):
        qris.parse(" \n")
    with pytest.raises(TypeError):
        qris.parse(None)  # type: ignore[arg-type]
    with pytest.raises(QRISParseError) as info:
        qris.parse("  0005012")
    assert info.value.position == 6
