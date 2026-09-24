from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

import qriskit
from helpers import STATIC
from qriskit import QRISParseError, QRISWarning, image

segno = pytest.importorskip("segno")


def test_png_bytes() -> None:
    data = image.to_png(qriskit.parse(STATIC))
    assert data.startswith(b"\x89PNG")


def test_svg_text() -> None:
    svg = image.to_svg(STATIC)
    assert svg.startswith("<svg")


def test_string_is_rendered_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = STATIC[:-4] + "0000"
    seen: list[str] = []
    real = segno.make_qr

    def spy(content: str, **kwargs: object) -> object:
        seen.append(content)
        return real(content, **kwargs)

    monkeypatch.setattr(segno, "make_qr", spy)
    image.to_svg(f"  {broken}\n")
    assert seen == [broken]


def test_invalid_string_is_rejected() -> None:
    with pytest.raises(QRISParseError):
        image.to_png("0005012")


def test_save_png_and_svg(tmp_path: Path) -> None:
    png = tmp_path / "qriskit.png"
    svg = tmp_path / "qriskit.SVG"
    image.save(STATIC, png)
    image.save(STATIC, svg)
    assert png.read_bytes().startswith(b"\x89PNG")
    assert svg.read_text(encoding="utf-8").startswith("<svg")


def test_save_rejects_unknown_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.png or \.svg"):
        image.save(STATIC, tmp_path / "qriskit.jpg")


def test_small_png_warns(tmp_path: Path) -> None:
    with pytest.warns(QRISWarning, match="115px"):
        image.to_png(STATIC, scale=1, border=0)
    with pytest.warns(QRISWarning):
        image.save(STATIC, tmp_path / "small.png", scale=1, border=0)


def test_default_size_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        image.to_png(STATIC)


def test_missing_segno_gives_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "segno", None)
    with pytest.raises(ImportError, match=r'pip install "qriskit\[image\]"'):
        image.to_png(STATIC)
