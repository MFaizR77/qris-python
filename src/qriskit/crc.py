"""CRC-16/CCITT-FALSE, the checksum stored in tag 63 of EMVCo QR codes."""

from __future__ import annotations

import binascii


def crc16(data: str) -> str:
    """Return the CRC-16/CCITT-FALSE of ``data`` as four uppercase hex digits.

    The text is UTF-8 encoded first. For a QRIS payload, ``data`` is everything
    up to and including ``"6304"``.
    """
    # crc_hqx uses polynomial 0x1021 without reflection; seeding it with 0xFFFF
    # gives exactly CCITT-FALSE.
    return format(binascii.crc_hqx(data.encode("utf-8"), 0xFFFF), "04X")
