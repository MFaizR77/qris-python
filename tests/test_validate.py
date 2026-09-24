from __future__ import annotations

import pytest

import qris
from helpers import STATIC, payload, static_pairs
from qris import Issue, QRISValidationError


def _swapped() -> list[tuple[str, str]]:
    """static_pairs() with tags 58 and 59 in the wrong order."""
    pairs = static_pairs()
    pairs[6], pairs[7] = pairs[7], pairs[6]
    return pairs


def codes(text: str) -> list[str]:
    return [issue.code for issue in qris.validate(text)]


def test_valid_sample_has_no_issues() -> None:
    assert qris.validate(STATIC) == []
    assert qris.is_valid(STATIC)


def test_validate_accepts_qris_objects() -> None:
    assert qris.validate(qris.parse(STATIC)) == []


def test_issue_str() -> None:
    issue = Issue("crc.mismatch", "error", "63", "bad")
    assert str(issue) == "error: crc.mismatch [63]: bad"
    assert str(Issue("tag.order", "warning", None, "x")) == "warning: tag.order: x"


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [
        # tag 00
        (static_pairs(t00=None), "pfi.invalid"),
        (static_pairs(t00="02"), "pfi.invalid"),
        ([("01", "11"), ("00", "01"), *static_pairs(t00=None, t01=None)], "pfi.invalid"),
        # required tags
        (static_pairs(t01=None), "tag.required"),
        (static_pairs(t52=None), "tag.required"),
        (static_pairs(t53=None), "tag.required"),
        (static_pairs(t58=None), "tag.required"),
        (static_pairs(t59=None), "tag.required"),
        (static_pairs(t60=None), "tag.required"),
        (static_pairs(t26=None, t51=None), "merchant_account.missing"),
        # structure
        ([*static_pairs(), ("59", "AGAIN")], "tag.duplicate"),
        (static_pairs(t62="0703ABC0703DEF"), "tag.duplicate"),
        (static_pairs(t62="07XX"), "template.malformed"),
        (static_pairs(t52="58A2"), "tag.format"),
        (static_pairs(t52="581"), "tag.format"),
        (static_pairs(t52=chr(0x665) + chr(0x668) + chr(0x661) + chr(0x662)), "tag.format"),
        (static_pairs(t59=""), "tag.format"),
        (static_pairs(t59="X" * 26), "tag.length"),
        (static_pairs(t60="X" * 16), "tag.length"),
        (static_pairs(t62="0726" + "X" * 26), "tag.length"),
        (static_pairs(t26="0014COM.GO-JEK.WWW0103ABC"), "tag.format"),
        # values
        (static_pairs(t01="13"), "poi.invalid"),
        (static_pairs(t53="156"), "currency.invalid"),
        (static_pairs(t58="SG"), "country.invalid"),
        ([*static_pairs(t01="12"), ("54", "0")], "amount.invalid"),
        ([*static_pairs(t01="12"), ("54", "1.234")], "amount.invalid"),
        ([*static_pairs(t01="12"), ("54", "1" * 14)], "amount.invalid"),
        ([*static_pairs(), ("55", "04")], "tip.invalid"),
        ([*static_pairs(), ("55", "02"), ("56", "abc")], "tip.invalid"),
        ([*static_pairs(), ("55", "03"), ("57", "100")], "tip.invalid"),
        ([*static_pairs(), ("55", "02")], "tip.value_missing"),
        ([*static_pairs(), ("55", "03")], "tip.value_missing"),
        ([*static_pairs(), ("56", "500")], "tip.orphan_value"),
        ([*static_pairs(), ("55", "02"), ("56", "500"), ("57", "5")], "tip.orphan_value"),
    ],
)
def test_error_codes(pairs: list[tuple[str, str]], expected: str) -> None:
    text = payload(*pairs)
    assert expected in codes(text)
    assert not qris.is_valid(text)
    with pytest.raises(QRISValidationError) as info:
        qris.parse(text, strict=True)
    assert expected in [i.code for i in info.value.issues]


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [
        (static_pairs(t61=None), "postal_code.missing"),
        (static_pairs(t51=None), "national.missing"),
        (static_pairs(t51="0015ID.CO.OTHER.WWW0215ID1020012345678"), "national.missing"),
        (static_pairs(t51="0014ID.CO.QRIS.WWW0303UMI"), "national.missing"),
        ([*static_pairs(), ("54", "1000")], "amount.on_static"),
        (static_pairs(t01="12"), "amount.missing_on_dynamic"),
        (_swapped(), "tag.order"),
    ],
)
def test_warning_codes(pairs: list[tuple[str, str]], expected: str) -> None:
    text = payload(*pairs)
    issues = qris.validate(text)
    assert expected in [i.code for i in issues]
    assert all(i.severity == "warning" for i in issues)
    assert qris.is_valid(text)
    qris.parse(text, strict=True)


def test_crc_missing() -> None:
    text = STATIC[:-8]
    assert codes(text) == ["crc.missing"]


def test_crc_mismatch_message_shows_expected_value() -> None:
    issues = qris.validate(STATIC[:-4] + "0000")
    assert [i.code for i in issues] == ["crc.mismatch"]
    assert "expected 3ACC" in issues[0].message


def test_crc_not_hex() -> None:
    assert codes(STATIC[:-4] + "ZZZZ") == ["crc.mismatch"]
    assert codes(STATIC[:-8] + "63023A") == ["crc.mismatch"]


def test_crc_lowercase_is_a_warning() -> None:
    lower = STATIC[:-4] + STATIC[-4:].lower()  # 3ACC -> 3acc
    assert codes(lower) == ["crc.lowercase"]
    assert qris.is_valid(lower)


def test_crc_not_last() -> None:
    text = STATIC + "9902AB"
    assert "crc.not_last" in codes(text)


def test_is_valid_never_raises() -> None:
    assert not qris.is_valid("garbage")
    assert not qris.is_valid("")
    assert not qris.is_valid(None)  # type: ignore[arg-type]


def test_strict_parse_passes_valid_payload() -> None:
    assert qris.parse(STATIC, strict=True).merchant_name == "TOKO CONTOH"


def test_validation_error_message_lists_errors() -> None:
    with pytest.raises(QRISValidationError, match=r"currency\.invalid"):
        qris.parse(payload(*static_pairs(t53="156")), strict=True)
