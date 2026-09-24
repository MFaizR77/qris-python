from __future__ import annotations

import qris
from helpers import STATIC, payload, static_pairs


def test_structure_and_lengths_are_kept() -> None:
    original = qris.parse(STATIC)
    masked = qris.anonymize(original)
    assert [n.tag for n in masked.nodes] == [n.tag for n in original.nodes]
    for before, after in zip(original.nodes, masked.nodes):
        assert len(before.value) == len(after.value)
    assert qris.validate(masked) == []


def test_sensitive_values_change_and_safe_ones_stay() -> None:
    original = qris.parse(STATIC)
    masked = qris.anonymize(original)
    assert masked.merchant_name != original.merchant_name
    assert masked.merchant_city != original.merchant_city
    assert masked.postal_code != original.postal_code
    assert masked.nmid != original.nmid and masked.nmid is not None
    assert masked.nmid.startswith("ID")
    gopay = masked.merchant_accounts[0]
    assert gopay.nns == "93600914"
    assert gopay.pan != original.merchant_accounts[0].pan
    assert gopay.merchant_id != original.merchant_accounts[0].merchant_id
    assert gopay.guid == "COM.GO-JEK.WWW"
    assert gopay.criteria == "UMI"
    assert masked.mcc == original.mcc
    assert masked.additional_data.terminal_label != "KASIR-01"
    assert masked.merchant_name is not None and " " in masked.merchant_name


def test_amount_and_tip_are_kept() -> None:
    dynamic = qris.parse(STATIC).to_dynamic(25000, tip=qris.Tip.fixed(500))
    masked = qris.anonymize(dynamic)
    assert masked.amount == dynamic.amount
    assert masked.tip == dynamic.tip


def test_deterministic_per_seed() -> None:
    q = qris.parse(STATIC)
    assert qris.anonymize(q, seed=1).dumps() == qris.anonymize(q, seed=1).dumps()
    assert qris.anonymize(q, seed=1).dumps() != qris.anonymize(q, seed=2).dumps()


def test_language_template_and_unreserved_templates() -> None:
    text = payload(
        *static_pairs(), ("64", "0002ID0104NAMA0202KT"), ("80", "0003ABC"), ("81", "junk")
    )
    masked = qris.anonymize(qris.parse(text))
    assert masked.get("64.00") == "ID"
    assert masked.get("64.01") != "NAMA"
    assert masked.get("80.00") != "ABC"
    assert masked.get("81") != "junk" and len(masked.get("81") or "") == 4
