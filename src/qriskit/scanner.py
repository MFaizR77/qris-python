"""Read QRIS payloads from images. Needs the optional ``zxing-cpp`` and ``Pillow`` packages.

Install them with ``pip install "qriskit[scan]"``. Everything runs locally; images
are never sent anywhere.
"""

from __future__ import annotations

import io
import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import spec
from .errors import QRISParseError, QRISScanError
from .model import QRIS, parse_payload
from .validate import parse

_INSTALL_HINT = (
    'Reading images needs the optional "zxing-cpp" and "Pillow" packages. '
    'Install them with: pip install "qriskit[scan]"'
)
_PREVIEW = 40


@dataclass(frozen=True)
class ScanResult:
    """One QR code found in an image."""

    text: str
    """The decoded text, exactly as stored in the QR code."""
    qris: QRIS | None
    """The parsed payload if the text is a QRIS, otherwise ``None``."""
    position: tuple[tuple[int, int], ...]
    """Corners (x, y): top-left, top-right, bottom-right, bottom-left."""

    @property
    def is_qris(self) -> bool:
        return self.qris is not None


def _deps() -> tuple[Any, Any]:
    try:
        import zxingcpp
        from PIL import Image
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc
    try:  # Optional HEIC support: used automatically when installed.
        from pillow_heif import register_heif_opener
    except ImportError:
        pass
    else:  # pragma: no cover - depends on an optional plugin
        register_heif_opener()
    return zxingcpp, Image


def _open(image: object, pil: Any) -> Any:
    if isinstance(image, pil.Image):
        return image
    if isinstance(image, str) and image.lstrip().startswith("000201"):
        raise QRISScanError(
            "unreadable_image",
            "This looks like a QRIS payload, not an image; use qriskit.parse() instead",
        )
    source: Any
    if isinstance(image, (bytes, bytearray, memoryview)):
        source = io.BytesIO(bytes(image))
    elif isinstance(image, (str, os.PathLike)):
        source = Path(image)
    elif hasattr(image, "read"):
        source = image
    else:
        raise TypeError(
            "image must be a path, bytes, a binary file object or a PIL image, "
            f"not {type(image).__name__}"
        )
    try:
        with warnings.catch_warnings():
            # Pillow only warns between 1x and 2x its pixel limit; for uploads from
            # strangers that is already too much, so treat the warning as an error.
            warnings.simplefilter("error", pil.DecompressionBombWarning)
            opened = pil.open(source)
            opened.load()
    except (pil.DecompressionBombError, pil.DecompressionBombWarning) as exc:
        raise QRISScanError("image_too_large", f"Image is too large to scan safely: {exc}") from exc
    except pil.UnidentifiedImageError as exc:
        raise QRISScanError(
            "unreadable_image",
            "Unsupported or corrupt image. PNG, JPEG, WEBP, BMP and GIF are supported; "
            "for iPhone HEIC photos install pillow-heif or convert to JPEG",
        ) from exc
    return opened


def _grayscale(image: Any, pil: Any) -> Any:
    # Transparent pixels are often black with alpha 0; flatten them onto white
    # first, or a QR on a transparent background disappears into black.
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = pil.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        image = background
    return image.convert("L")


def _text(barcode: Any) -> str:
    # Decode the raw bytes as UTF-8 ourselves: QR codes often omit the charset
    # marker, and guessing Latin-1 would garble non-ASCII merchant names.
    raw = bytes(barcode.bytes)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return str(barcode.text)


def _corners(barcode: Any) -> tuple[tuple[int, int], ...]:
    p = barcode.position
    points = (p.top_left, p.top_right, p.bottom_right, p.bottom_left)
    return tuple((int(point.x), int(point.y)) for point in points)


def _as_qris(text: str) -> QRIS | None:
    """The parsed payload if ``text`` is an Indonesian QRIS, else ``None``."""
    if not text.startswith("000201"):
        return None
    try:
        qris = parse_payload(text)
    except QRISParseError:
        return None
    if qris.country == spec.COUNTRY_ID or qris.national is not None:
        return qris
    return None


def _binarized(image: Any) -> Any:
    """High-contrast black and white copy, for decoders that struggle with artifacts."""
    from PIL import ImageOps

    return ImageOps.autocontrast(image).point(lambda value: 255 if value > 128 else 0)


def scan_all(image: object) -> list[ScanResult]:
    """Every QR code in ``image``, QRIS or not, without duplicates.

    ``image`` may be a file path, the file's bytes, a binary file object (such
    as an upload) or a ``PIL.Image.Image``.
    """
    zxingcpp, pil = _deps()
    picture = _grayscale(_open(image, pil), pil)
    results: list[ScanResult] = []
    seen: set[str] = set()

    def read(candidate: Any) -> None:
        found = zxingcpp.read_barcodes(candidate, formats=zxingcpp.BarcodeFormat.QRCode)
        for barcode in found:
            text = _text(barcode)
            if text not in seen:
                seen.add(text)
                results.append(ScanResult(text, _as_qris(text), _corners(barcode)))

    read(picture)
    if not any(result.is_qris for result in results):
        # Older zxing-cpp releases (used on Python 3.9) miss codes in lossy
        # WEBP/JPEG images that a thresholded copy reads fine.
        read(_binarized(picture))
    return results


def select_qris(results: Sequence[ScanResult]) -> ScanResult:
    """The single QRIS among ``results``; raises :class:`QRISScanError` otherwise."""
    if not results:
        raise QRISScanError(
            "no_qr",
            "No QR code found. Use a sharper, well-lit image in which the QR code "
            "is at least about 150 pixels wide",
        )
    found = [result for result in results if result.is_qris]
    if not found:
        previews = ", ".join(repr(r.text[:_PREVIEW]) for r in results)
        raise QRISScanError(
            "no_qris", f"Found {len(results)} QR code(s) but none is a QRIS: {previews}"
        )
    if len(found) > 1:
        raise QRISScanError(
            "multiple_qris",
            f"Found {len(found)} different QRIS codes; use qriskit.scan_all() to choose one",
        )
    return found[0]


def scan(image: object, *, strict: bool = False) -> QRIS:
    """Read the one QRIS in ``image``.

    QR codes that are not QRIS are ignored. Raises :class:`QRISScanError` when
    the image has no QR code, no QRIS, or more than one different QRIS. The
    payload is parsed like :func:`qriskit.parse`, so ``strict=True`` also raises
    :class:`QRISValidationError` for rule violations.
    """
    return parse(select_qris(scan_all(image)).text, strict=strict)
