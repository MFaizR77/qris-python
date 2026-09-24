"""Reading QRIS from images. Images are generated here, so no binary fixtures are stored."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

import qriskit
from helpers import EMVCO_SAMPLE, STATIC, payload, static_pairs
from qriskit import QRISScanError, QRISValidationError

zxingcpp = pytest.importorskip("zxingcpp")
Image = pytest.importorskip("PIL.Image")
ImageFilter = pytest.importorskip("PIL.ImageFilter")
ImageOps = pytest.importorskip("PIL.ImageOps")
segno = pytest.importorskip("segno")

UTF8 = payload(*static_pairs(t59="KOPI SÜSU 咖啡"))
OTHER = payload(*static_pairs(t59="TOKO LAIN"))


def qr(text: str, *, scale: int = 8, border: int = 4, eci: bool = False) -> Any:
    buffer = io.BytesIO()
    code = segno.make_qr(text, error="m", boost_error=False, eci=eci)
    code.save(buffer, kind="png", scale=scale, border=border)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def png_bytes(image: Any, kind: str = "PNG", **options: Any) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, kind, **options)
    return buffer.getvalue()


def side_by_side(*images: Any) -> Any:
    width = sum(i.width for i in images) + 40 * len(images)
    canvas = Image.new("RGB", (width, max(i.height for i in images) + 40), "white")
    x = 20
    for image in images:
        canvas.paste(image, (x, 20))
        x += image.width + 40
    return canvas


# ---- inputs -------------------------------------------------------------------


def test_scan_pil_image() -> None:
    q = qriskit.scan(qr(STATIC))
    assert q.dumps() == STATIC
    assert q.nmid == "ID1020012345678"


def test_scan_path_and_str_path(tmp_path: Path) -> None:
    target = tmp_path / "qriskit.png"
    target.write_bytes(png_bytes(qr(STATIC)))
    assert qriskit.scan(target).dumps() == STATIC
    assert qriskit.scan(str(target)).dumps() == STATIC


@pytest.mark.parametrize("wrap", [bytes, bytearray, memoryview, io.BytesIO])
def test_scan_bytes_and_file_objects(wrap: Any) -> None:
    assert qriskit.scan(wrap(png_bytes(qr(STATIC)))).dumps() == STATIC


class _OneWayStream(io.RawIOBase):
    """A non-seekable stream, like a raw HTTP request body."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def readinto(self, buffer: Any) -> int:
        return self._data.readinto(buffer)


def test_upload_that_was_already_read() -> None:
    upload = io.BytesIO(png_bytes(qr(STATIC)))
    upload.read()
    assert qriskit.scan(upload).dumps() == STATIC


def test_non_seekable_stream() -> None:
    stream = io.BufferedReader(_OneWayStream(png_bytes(qr(STATIC))))
    assert qriskit.scan(stream).dumps() == STATIC


def test_payload_text_gets_a_hint() -> None:
    with pytest.raises(QRISScanError, match=r"qriskit\.parse") as info:
        qriskit.scan(STATIC)
    assert info.value.reason == "unreadable_image"


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        qriskit.scan(tmp_path / "missing.png")


def test_wrong_type() -> None:
    with pytest.raises(TypeError, match="binary file object"):
        qriskit.scan(123)


# ---- image conditions -------------------------------------------------------


@pytest.mark.parametrize(
    "transform",
    [
        pytest.param(lambda im: im.rotate(17, expand=True, fillcolor="white"), id="rotated"),
        pytest.param(lambda im: im.filter(ImageFilter.GaussianBlur(1.5)), id="blurred"),
        pytest.param(lambda im: ImageOps.invert(im), id="inverted"),
        pytest.param(lambda im: im.convert("L"), id="grayscale"),
        pytest.param(lambda im: im.convert("1"), id="black-and-white"),
        pytest.param(
            lambda im: Image.open(io.BytesIO(png_bytes(im, "JPEG", quality=20))), id="jpeg-q20"
        ),
        pytest.param(
            lambda im: Image.open(io.BytesIO(png_bytes(im, "WEBP", quality=20))), id="webp-q20"
        ),
    ],
)
def test_hard_images(transform: Any) -> None:
    assert qriskit.scan(transform(qr(STATIC))).dumps() == STATIC


def test_sticker_like_poster() -> None:
    poster = Image.new("RGB", (1200, 1600), (230, 30, 40))
    poster.paste(Image.new("RGB", (900, 1000), "white"), (150, 300))
    poster.paste(qr(STATIC), (250, 380))
    assert qriskit.scan(poster).dumps() == STATIC


def test_transparent_background_png() -> None:
    """Transparent pixels are black with alpha 0; they must become white, not black."""
    modules = qr(STATIC).convert("L")
    transparent = Image.new("RGBA", modules.size, (0, 0, 0, 0))
    transparent.putalpha(ImageOps.invert(modules))
    assert qriskit.scan(png_bytes(transparent)).dumps() == STATIC


def test_palette_png_with_transparency() -> None:
    image = qr(STATIC).convert("P")
    image.info["transparency"] = 255
    assert qriskit.scan(png_bytes(image)).dumps() == STATIC


@pytest.mark.parametrize("eci", [False, True])
def test_non_ascii_merchant_name(eci: bool) -> None:
    q = qriskit.scan(qr(UTF8, eci=eci))
    assert q.merchant_name == "KOPI SÜSU 咖啡"
    assert qriskit.validate(q) == []


def test_non_utf8_bytes_fall_back_to_decoder_text() -> None:
    buffer = io.BytesIO()
    segno.make_qr(b"caf" + bytes([0xE9]), error="m").save(buffer, kind="png", scale=8, border=4)
    (result,) = qriskit.scan_all(buffer.getvalue())
    assert result.text == "caf" + chr(0xE9)
    assert not result.is_qris


# ---- several / zero / non-QRIS codes ---------------------------------------


def test_qris_next_to_other_qr_is_found() -> None:
    image = side_by_side(qr("https://instagram.com/tokocontoh", scale=5), qr(STATIC, scale=5))
    assert qriskit.scan(image).dumps() == STATIC
    results = qriskit.scan_all(image)
    assert sorted(r.is_qris for r in results) == [False, True]


def test_same_qris_twice_counts_once() -> None:
    image = side_by_side(qr(STATIC, scale=5), qr(STATIC, scale=5))
    assert len(qriskit.scan_all(image)) == 1
    assert qriskit.scan(image).dumps() == STATIC


def test_two_different_qris() -> None:
    image = side_by_side(qr(STATIC, scale=5), qr(OTHER, scale=5))
    with pytest.raises(QRISScanError, match=r"scan_all") as info:
        qriskit.scan(image)
    assert info.value.reason == "multiple_qris"
    assert {r.text for r in qriskit.scan_all(image)} == {STATIC, OTHER}


def test_no_qr_code() -> None:
    with pytest.raises(QRISScanError, match="150 pixels") as info:
        qriskit.scan(Image.new("RGB", (400, 400), "white"))
    assert info.value.reason == "no_qr"
    assert qriskit.scan_all(Image.new("RGB", (400, 400), "white")) == []


def test_too_small_image_reports_no_qr() -> None:
    with pytest.raises(QRISScanError) as info:
        qriskit.scan(qr(STATIC).resize((70, 70)))
    assert info.value.reason == "no_qr"


@pytest.mark.parametrize("text", ["https://example.com/pay", EMVCO_SAMPLE, "000201 not tlv"])
def test_non_qris_code(text: str) -> None:
    with pytest.raises(QRISScanError, match="none is a QRIS") as info:
        qriskit.scan(qr(text))
    assert info.value.reason == "no_qris"
    assert qriskit.scan_all(qr(text))[0].qris is None


def test_qris_without_country_but_with_national_account() -> None:
    text = payload(*static_pairs(t58=None))
    assert qriskit.scan(qr(text)).nmid == "ID1020012345678"


# ---- validation --------------------------------------------------------------


def test_broken_crc_is_returned_leniently_and_rejected_strictly() -> None:
    broken = STATIC[:-4] + "0000"
    image = qr(broken)
    assert qriskit.scan(image).crc == "0000"
    assert qriskit.scan_all(image)[0].text == broken
    with pytest.raises(QRISValidationError, match=r"crc\.mismatch"):
        qriskit.scan(image, strict=True)


def test_scan_result_position() -> None:
    (result,) = qriskit.scan_all(qr(STATIC))
    assert len(result.position) == 4
    assert all(isinstance(v, int) for point in result.position for v in point)
    xs = [x for x, _ in result.position]
    assert max(xs) - min(xs) > 100


# ---- unreadable and hostile inputs -------------------------------------------


def test_not_an_image() -> None:
    with pytest.raises(QRISScanError, match="pillow-heif") as info:
        qriskit.scan(b"definitely not an image")
    assert info.value.reason == "unreadable_image"


@pytest.mark.parametrize("side", [40, 100])
def test_decompression_bomb_is_rejected(monkeypatch: pytest.MonkeyPatch, side: int) -> None:
    """40x40 only triggers Pillow's warning, 100x100 its error; both must be refused."""
    data = png_bytes(Image.new("L", (side, side), 255))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(QRISScanError) as info:
        qriskit.scan(data)
    assert info.value.reason == "image_too_large"


def test_missing_dependencies_give_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "zxingcpp", None)
    with pytest.raises(ImportError, match=r'pip install "qriskit\[scan\]"'):
        qriskit.scan(qr(STATIC))
