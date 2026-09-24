from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import qriskit
from helpers import STATIC, payload, static_pairs
from qriskit.cli import main


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_decode_table(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "decode", STATIC)
    assert code == 0
    assert "TOKO CONTOH (JAKARTA 10110)" in out
    assert "ID1020012345678" in out
    assert "KASIR-01" in out
    assert "NNS 93600914 (GoPay)" in out
    assert "3ACC OK" in out


def test_decode_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "decode", STATIC, "--json")
    assert code == 0
    assert json.loads(out)["nmid"] == "ID1020012345678"


def test_decode_shows_crc_mismatch_and_dynamic_fields(capsys: pytest.CaptureFixture[str]) -> None:
    dynamic = qriskit.parse(STATIC).to_dynamic(25000, tip=qriskit.Tip.fixed(500), reference="INV-1")
    _, out, _ = run(capsys, "decode", dynamic.dumps()[:-4] + "0000")
    assert "MISMATCH" in out
    assert "25000" in out and "fixed 500" in out and "INV-1" in out


def test_decode_minimal_payload(capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run(capsys, "decode", payload(("00", "01"), ("26", "0003ABC"))[:-8])
    assert "missing" in out and "unknown" in out


def test_validate_ok_and_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "validate", STATIC) == (0, "OK: no issues found\n", "")
    code, out, _ = run(capsys, "validate", STATIC[:-4] + "0000")
    assert code == 1
    assert "crc.mismatch" in out


def test_validate_json_and_warnings(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "validate", payload(*static_pairs(t61=None)), "--json")
    assert code == 0
    assert json.loads(out)[0]["code"] == "postal_code.missing"


def test_dynamic_and_static(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "dynamic", STATIC, "--amount", "25000", "--fee", "500")
    assert code == 0
    dynamic = qriskit.parse(out.strip())
    assert dynamic.amount == 25000 and dynamic.get("56") == "500"
    _, out, _ = run(capsys, "dynamic", STATIC, "--amount", "1000", "--fee-percent", "1.5")
    assert qriskit.parse(out.strip()).get("57") == "1.50"
    _, out, _ = run(capsys, "dynamic", STATIC, "--amount", "1000", "--tip", "--reference", "R1")
    tipped = qriskit.parse(out.strip())
    assert tipped.get("55") == "01" and tipped.additional_data.reference_label == "R1"
    _, out, _ = run(capsys, "static", dynamic.dumps())
    assert out.strip() == STATIC


def test_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(STATIC + "\n"))
    code, out, _ = run(capsys, "validate", "-")
    assert code == 0 and "OK" in out


def test_errors_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "decode", "0005012")
    assert code == 2 and err.startswith("error:")
    code, _, err = run(capsys, "dynamic", STATIC, "--amount", "-1")
    assert code == 2 and "not a plain positive number" in err
    code, _, err = run(capsys, "dynamic", STATIC[:-4] + "0000", "--amount", "1")
    assert code == 2 and "crc.mismatch" in err


def test_usage_error_exits_2() -> None:
    with pytest.raises(SystemExit) as info:
        main(["dynamic", STATIC])
    assert info.value.code == 2


def test_image(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    pytest.importorskip("segno")
    target = tmp_path / "q.png"
    code, out, _ = run(capsys, "image", STATIC, "-o", str(target))
    assert code == 0 and target.exists() and "Saved" in out


def test_anonymize(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "anonymize", STATIC, "--seed", "3")
    assert code == 0
    assert qriskit.parse(out.strip()).merchant_name != "TOKO CONTOH"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert qriskit.__version__ in capsys.readouterr().out


def test_python_dash_m() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "qriskit", "validate", STATIC],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_non_ascii_name_on_non_utf8_stdout() -> None:
    text = payload(*static_pairs(t59="咖啡店"))
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-m", "qriskit", "decode", text],
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert b"Merchant" in result.stdout


def _qr_png(text: str) -> bytes:
    segno = pytest.importorskip("segno")
    pytest.importorskip("zxingcpp")
    buffer = io.BytesIO()
    segno.make_qr(text, error="m").save(buffer, kind="png", scale=8, border=4)
    return buffer.getvalue()


def test_scan(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    image = tmp_path / "qriskit.png"
    image.write_bytes(_qr_png(STATIC))
    code, out, _ = run(capsys, "scan", str(image))
    assert code == 0 and out.strip() == STATIC


def test_scan_from_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(_qr_png(STATIC))))
    code, out, _ = run(capsys, "scan", "-")
    assert code == 0 and out.strip() == STATIC


def test_scan_all(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    image = tmp_path / "url.png"
    image.write_bytes(_qr_png("https://example.com"))
    code, out, _ = run(capsys, "scan", str(image), "--all")
    assert code == 0 and out.strip() == "https://example.com"
    code, out, _ = run(capsys, "scan", str(image), "--all", "--json")
    rows = json.loads(out)
    assert rows[0]["is_qris"] is False and len(rows[0]["position"]) == 4


def test_scan_errors_exit_2(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    image = tmp_path / "url.png"
    image.write_bytes(_qr_png("https://example.com"))
    code, _, err = run(capsys, "scan", str(image))
    assert code == 2 and "none is a QRIS" in err
    code, _, err = run(capsys, "scan", str(tmp_path / "missing.png"))
    assert code == 2 and err.startswith("error:")
