"""Random input must never crash with anything but QRISParseError."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

import qriskit
from helpers import STATIC
from qriskit import QRISParseError

tlv_alphabet = st.sampled_from("0123456789ABCXYZ .-😀")


@settings(max_examples=300, deadline=None)
@given(st.text())
def test_parse_any_text(text: str) -> None:
    try:
        q = qriskit.parse(text)
    except QRISParseError:
        return
    qriskit.validate(q)
    q.to_dict()


@settings(max_examples=300, deadline=None)
@given(st.text(alphabet=tlv_alphabet, max_size=120))
def test_parse_tlv_like_text(text: str) -> None:
    try:
        q = qriskit.parse(text)
    except QRISParseError:
        return
    qriskit.validate(q)
    q.to_dict()
    assert qriskit.parse(q.dumps()).nodes[:-1] == tuple(n for n in q.nodes if n.tag != "63")


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=0, max_value=len(STATIC) - 1), st.characters())
def test_single_character_corruption_is_detected(index: int, char: str) -> None:
    corrupted = STATIC[:index] + char + STATIC[index + 1 :]
    lowercased_crc = index >= len(STATIC) - 4 and char.upper() == STATIC[index]
    if char == STATIC[index] or lowercased_crc:
        return
    assert not qriskit.is_valid(corrupted)


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=1, max_value=10**12))
def test_any_valid_amount_round_trips(amount: int) -> None:
    d = qriskit.parse(STATIC).to_dynamic(amount)
    assert qriskit.validate(d) == []
    assert d.amount == amount
    assert d.to_static().dumps() == STATIC
