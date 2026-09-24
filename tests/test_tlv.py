from __future__ import annotations

import pytest

from qriskit.errors import QRISParseError
from qriskit.tlv import Node, decode, encode


def test_decode_simple() -> None:
    assert decode("000201010211") == (Node("00", "01"), Node("01", "11"))


def test_decode_empty_string_is_empty_tuple() -> None:
    assert decode("") == ()


def test_zero_length_value() -> None:
    assert decode("6200") == (Node("62", ""),)


def test_length_counts_characters_not_bytes() -> None:
    assert decode("0104最佳运输") == (Node("01", "最佳运输"),)


def test_encode_roundtrip() -> None:
    text = "00020101021159051234560021X"
    nodes = decode(text)
    assert encode(nodes) == text


def test_value_of_99_characters() -> None:
    value = "x" * 99
    assert decode("59" + "99" + value) == (Node("59", value),)


def test_encode_rejects_values_over_99() -> None:
    with pytest.raises(ValueError, match="maximum is 99"):
        Node("59", "x" * 100).encode()


def test_node_rejects_bad_tag() -> None:
    with pytest.raises(ValueError, match="two digits"):
        Node("5A", "x")


@pytest.mark.parametrize(
    ("data", "message", "position"),
    [
        ("000", "Truncated element", 0),
        ("0002010", "Truncated element", 6),
        ("AB0201", "Invalid tag 'AB'", 0),
        ("00X201", "Invalid length 'X2'", 2),
        ("0005012", "declares 5 characters but only 3 remain", 4),
        ("0²0201", "Invalid tag", 0),
    ],
)
def test_decode_errors_have_positions(data: str, message: str, position: int) -> None:
    with pytest.raises(QRISParseError, match=message) as info:
        decode(data)
    assert info.value.position == position


def test_offset_is_added_to_positions() -> None:
    with pytest.raises(QRISParseError) as info:
        decode("0005012", offset=100)
    assert info.value.position == 104
