"""Render a QRIS payload as a QR code image. Needs the optional ``segno`` package.

Install it with ``pip install "qriskit[image]"``.
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path
from typing import Any, Union

from .errors import QRISWarning
from .model import QRIS
from .validate import parse

MIN_PIXELS = 115
"""ASPI's minimum QR size for QRIS (Buletin ASPI No. 3/III/2021)."""

PathLike = Union[str, Path]


def _segno() -> Any:
    try:
        import segno
    except ImportError as exc:
        raise ImportError(
            'Rendering images needs the optional "segno" package. '
            'Install it with: pip install "qriskit[image]"'
        ) from exc
    return segno


def _qr(payload: QRIS | str, error: str) -> Any:
    # A string is rendered exactly as given (after trimming), so a broken CRC is not hidden.
    text = payload.dumps() if isinstance(payload, QRIS) else payload.strip()
    if not isinstance(payload, QRIS):
        parse(text)
    return _segno().make_qr(text, error=error.lower(), boost_error=False)


def _warn_if_small(qr: Any, scale: int, border: int) -> None:
    width = qr.symbol_size(scale=scale, border=border)[0]
    if width < MIN_PIXELS:
        warnings.warn(
            f"QR image is {width}px wide; ASPI requires at least {MIN_PIXELS}px",
            QRISWarning,
            stacklevel=3,
        )


def to_png(payload: QRIS | str, *, scale: int = 10, border: int = 4, error: str = "M") -> bytes:
    """PNG bytes of the QR code."""
    qr = _qr(payload, error)
    _warn_if_small(qr, scale, border)
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=scale, border=border)
    return buffer.getvalue()


def to_svg(payload: QRIS | str, *, scale: int = 10, border: int = 4, error: str = "M") -> str:
    """SVG text of the QR code."""
    buffer = io.BytesIO()
    _qr(payload, error).save(buffer, kind="svg", scale=scale, border=border, xmldecl=False)
    return buffer.getvalue().decode("utf-8")


def save(
    payload: QRIS | str,
    path: PathLike,
    *,
    scale: int = 10,
    border: int = 4,
    error: str = "M",
) -> None:
    """Write the QR code to ``path``; the format follows the extension (.png or .svg)."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".png":
        qr = _qr(payload, error)
        _warn_if_small(qr, scale, border)
        qr.save(str(target), kind="png", scale=scale, border=border)
    elif suffix == ".svg":
        target.write_text(
            to_svg(payload, scale=scale, border=border, error=error), encoding="utf-8"
        )
    else:
        raise ValueError(f"Unsupported image type {target.suffix!r}; use .png or .svg")
