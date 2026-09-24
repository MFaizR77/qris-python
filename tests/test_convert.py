from __future__ import annotations

import json
from decimal import Decimal

import pytest

import qriskit
from helpers import STATIC, payload, static_pairs
from qriskit import MerchantAccount, QRISValidationError, Tip


def test_to_dynamic_sets_amount_in_order() -> None:
    d = qriskit.parse(STATIC).to_dynamic(25000)
    assert d.is_dynamic
    assert d.amount == Decimal("25000")
    tags = [node.tag for node in d.nodes]
    assert tags == ["00", "01", "26", "51", "52", "53", "54", "58", "59", "60", "61", "62", "63"]
    assert qriskit.validate(d) == []
    assert qriskit.parse(d.dumps()).dumps() == d.dumps()


def test_to_dynamic_keeps_every_other_tag() -> None:
    source = qriskit.parse(STATIC)
    d = source.to_dynamic(10000)
    untouched = {"00", "26", "51", "52", "53", "58", "59", "60", "61", "62"}
    for tag in untouched:
        assert d.get(tag) == source.get(tag)


def test_to_dynamic_with_tips() -> None:
    q = qriskit.parse(STATIC)
    fixed = q.to_dynamic(25000, tip=Tip.fixed(1000))
    assert (fixed.get("55"), fixed.get("56"), fixed.get("57")) == ("02", "1000", None)
    percent = q.to_dynamic(25000, tip=Tip.percent("2.5"))
    assert (percent.get("55"), percent.get("56"), percent.get("57")) == ("03", None, "2.50")
    prompt = q.to_dynamic(25000, tip=Tip.prompt())
    assert (prompt.get("55"), prompt.get("56"), prompt.get("57")) == ("01", None, None)
    for result in (fixed, percent, prompt):
        assert qriskit.validate(result) == []


def test_to_dynamic_with_reference() -> None:
    d = qriskit.parse(STATIC).to_dynamic(25000, reference="INV-2026-001")
    assert d.additional_data.reference_label == "INV-2026-001"
    assert d.additional_data.terminal_label == "KASIR-01"
    assert d.get("62") == "0512INV-2026-0010708KASIR-01"


def test_to_dynamic_creates_tag_62_for_reference() -> None:
    q = qriskit.parse(payload(*static_pairs(t62=None)))
    assert q.to_dynamic(5000, reference="A1").get("62") == "0502A1"


@pytest.mark.parametrize("reference", ["", "X" * 26])
def test_to_dynamic_rejects_bad_reference(reference: str) -> None:
    with pytest.raises(ValueError, match="1 to 25"):
        qriskit.parse(STATIC).to_dynamic(1000, reference=reference)


def test_to_dynamic_on_dynamic_replaces_amount_and_tip() -> None:
    first = qriskit.parse(STATIC).to_dynamic(25000, tip=Tip.fixed(1000))
    second = first.to_dynamic(30000)
    assert second.amount == Decimal("30000")
    assert second.tip is None
    assert [n.tag for n in second.nodes].count("54") == 1


def test_to_dynamic_rejects_broken_crc() -> None:
    broken = qriskit.parse(STATIC[:-4] + "0000")
    with pytest.raises(QRISValidationError, match=r"crc\.mismatch"):
        broken.to_dynamic(1000)
    with pytest.raises(QRISValidationError, match=r"crc\.missing"):
        qriskit.parse(STATIC[:-8]).to_dynamic(1000)


def test_to_dynamic_allows_lowercase_crc() -> None:
    lower = qriskit.parse(STATIC[:-4] + STATIC[-4:].lower())
    assert lower.to_dynamic(1000).is_dynamic


@pytest.mark.parametrize("amount", [0, -1, "1e3", "1.234", 10**13])
def test_to_dynamic_rejects_bad_amounts(amount: object) -> None:
    with pytest.raises(ValueError):
        qriskit.parse(STATIC).to_dynamic(amount)  # type: ignore[arg-type]


def test_to_dynamic_rejects_float_and_bad_tip() -> None:
    with pytest.raises(TypeError, match="float"):
        qriskit.parse(STATIC).to_dynamic(0.1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"qriskit\.Tip"):
        qriskit.parse(STATIC).to_dynamic(1000, tip="02")  # type: ignore[arg-type]


def test_to_static() -> None:
    d = qriskit.parse(STATIC).to_dynamic(25000, tip=Tip.fixed(1000))
    s = d.to_static()
    assert s.is_static
    assert s.amount is None and s.tip is None
    assert s.dumps() == STATIC


def test_with_tag_root_and_nested() -> None:
    q = qriskit.parse(STATIC)
    assert q.with_tag("61", "40111").postal_code == "40111"
    changed = q.with_tag("62.01", "BILL-9")
    assert changed.get("62") == "0106BILL-90708KASIR-01"
    assert qriskit.validate(changed) == []


def test_with_tag_inserts_new_root_tag_in_order() -> None:
    q = qriskit.parse(payload(*static_pairs(t61=None)))
    tags = [n.tag for n in q.with_tag("61", "10110").nodes]
    assert tags.index("61") == tags.index("60") + 1


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("63", "managed"),
        ("00", "managed"),
        ("5", "Invalid tag path"),
        ("62.5", "Invalid tag path"),
        ("59.01", "not a template"),
    ],
)
def test_with_tag_rejects_bad_paths(path: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        qriskit.parse(STATIC).with_tag(path, "X")


def test_with_tag_rejects_too_long_and_non_string() -> None:
    with pytest.raises(ValueError, match="maximum is 99"):
        qriskit.parse(STATIC).with_tag("80", "X" * 100)
    with pytest.raises(TypeError):
        qriskit.parse(STATIC).with_tag("59", 5)  # type: ignore[arg-type]


def test_with_tag_on_malformed_template() -> None:
    q = qriskit.parse(payload(*static_pairs(t62="07XX")))
    with pytest.raises(ValueError, match="malformed"):
        q.with_tag("62.05", "A")


def test_without_tag() -> None:
    q = qriskit.parse(STATIC)
    assert q.without_tag("61").postal_code is None
    assert q.without_tag("62.07").get("62") is None
    assert q.without_tag("64.01").dumps() == STATIC
    assert q.without_tag("64").dumps() == STATIC
    two = q.with_tag("62.05", "R")
    assert two.without_tag("62.05").dumps() == STATIC


def test_build_round_trips_and_validates() -> None:
    built = qriskit.build(
        merchant_name="TOKO CONTOH",
        merchant_city="JAKARTA",
        mcc="5812",
        postal_code="10110",
        accounts=[
            MerchantAccount.national(nmid="ID1020012345678", criteria="UMI"),
            MerchantAccount.create(
                tag="26",
                guid="COM.GO-JEK.WWW",
                pan="9360091412345678901",
                merchant_id="G123456789",
                criteria="UMI",
            ),
        ],
        additional_data={"07": "KASIR-01"},
    )
    assert built.dumps() == STATIC


def test_build_dynamic_with_tip() -> None:
    built = qriskit.build(
        merchant_name="A",
        merchant_city="B",
        mcc="5812",
        accounts=[MerchantAccount.create(tag="26", guid="COM.GO-JEK.WWW", pan="93600914123")],
        amount="15000.50",
        tip=Tip.fixed(500),
    )
    assert built.is_dynamic
    assert built.amount == Decimal("15000.50")
    assert [i.code for i in qriskit.validate(built)] == ["national.missing", "postal_code.missing"]


def test_build_rejects_invalid_results() -> None:
    account = MerchantAccount.national(nmid="ID1")
    with pytest.raises(QRISValidationError, match=r"tag\.length"):
        qriskit.build(merchant_name="X" * 26, merchant_city="B", mcc="5812", accounts=[account])
    with pytest.raises(ValueError, match="At least one"):
        qriskit.build(merchant_name="A", merchant_city="B", mcc="5812", accounts=[])
    with pytest.raises(ValueError, match="unique"):
        qriskit.build(merchant_name="A", merchant_city="B", mcc="5812", accounts=[account, account])


def test_to_dict_of_dynamic() -> None:
    q = qriskit.parse(STATIC).to_dynamic(25000, tip=Tip.percent("2.5"), reference="INV-1")
    data = json.loads(json.dumps(q.to_dict()))
    assert data["merchant_name"] == "TOKO CONTOH"
    assert data["amount"] == "25000"
    assert data["tip"] == {"kind": "percent", "value": "2.50"}
    assert data["nmid"] == "ID1020012345678"
    assert data["merchant_accounts"][0]["acquirer"] == "GoPay"
    assert data["merchant_accounts"][1]["acquirer"] is None
    assert data["additional_data"] == {"reference_label": "INV-1", "terminal_label": "KASIR-01"}
    assert data["payload"] == q.dumps()


def test_reference_that_overflows_tag_62_is_rejected() -> None:
    full = qriskit.parse(payload(*static_pairs(t62="0170" + "B" * 70 + "0708KASIR-01")))
    with pytest.raises(ValueError, match="Value for tag 62"):
        full.to_dynamic(1000, reference="X" * 25)


def test_to_dynamic_adds_missing_point_of_initiation() -> None:
    d = qriskit.parse(payload(*static_pairs(t01=None))).to_dynamic(1000)
    assert [n.tag for n in d.nodes][:2] == ["00", "01"]
    assert d.is_dynamic
