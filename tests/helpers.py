"""Shared test data. Payloads are synthetic; none belongs to a real merchant."""

from __future__ import annotations

from qriskit import tlv
from qriskit.crc import crc16

GOPAY_ACCOUNT = "0014COM.GO-JEK.WWW011993600914123456789010210G1234567890303UMI"
NATIONAL_ACCOUNT = "0014ID.CO.QRIS.WWW0215ID10200123456780303UMI"

# Static QRIS with a GoPay account, national account (NMID) and terminal label.
STATIC = (
    "00020101021126620014COM.GO-JEK.WWW011993600914123456789010210G1234567890303UMI"
    "51440014ID.CO.QRIS.WWW0215ID10200123456780303UMI5204581253033605802ID"
    "5911TOKO CONTOH6007JAKARTA61051011062120708KASIR-0163043ACC"
)

# Example payload from the EMVCo MPM specification (CRC A13A). Not a QRIS.
EMVCO_SAMPLE = (
    "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812345678"
    "520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104最佳运输0202北京"
    "540523.7253031565502016233030412340603***0708A60086670902ME9132001"
    "6A0112233449988770708123456786304A13A"
)


def payload(*pairs: tuple[str, str], crc: str | None = None) -> str:
    """Encode (tag, value) pairs and append tag 63.

    ``crc`` overrides the checksum; by default the correct one is computed.
    """
    body = tlv.encode(tlv.Node(tag, value) for tag, value in pairs) + "6304"
    return body + (crc if crc is not None else crc16(body))


def static_pairs(**replace: str | None) -> list[tuple[str, str]]:
    """The pairs of STATIC (minus CRC). Pass ``t59="X"`` to replace, ``t61=None`` to drop."""
    pairs = [
        ("00", "01"),
        ("01", "11"),
        ("26", GOPAY_ACCOUNT),
        ("51", NATIONAL_ACCOUNT),
        ("52", "5812"),
        ("53", "360"),
        ("58", "ID"),
        ("59", "TOKO CONTOH"),
        ("60", "JAKARTA"),
        ("61", "10110"),
        ("62", "0708KASIR-01"),
    ]
    result = []
    for tag, value in pairs:
        key = f"t{tag}"
        if key in replace:
            if replace[key] is not None:
                result.append((tag, replace[key]))
        else:
            result.append((tag, value))
    return result
