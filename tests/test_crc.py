from __future__ import annotations

from helpers import EMVCO_SAMPLE, STATIC
from qriskit.crc import crc16


def reference_crc16(data: bytes) -> int:
    """Bit-by-bit CRC-16/CCITT-FALSE, written independently as an oracle."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def test_standard_check_value() -> None:
    assert crc16("123456789") == "29B1"


def test_empty_string() -> None:
    assert crc16("") == "FFFF"


def test_emvco_sample_with_non_ascii_text() -> None:
    assert crc16(EMVCO_SAMPLE[:-4]) == "A13A"


def test_matches_reference_implementation() -> None:
    for text in ["", "a", STATIC[:-4], "KOPI SÜSU", "😀 emoji"]:
        assert crc16(text) == format(reference_crc16(text.encode("utf-8")), "04X")


def test_output_is_four_uppercase_hex_digits() -> None:
    value = crc16("0002010102115802ID6304")
    assert len(value) == 4
    assert value == value.upper()
