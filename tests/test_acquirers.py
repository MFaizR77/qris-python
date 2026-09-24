from __future__ import annotations

import json
from importlib import resources

import pytest

from qriskit import acquirers
from qriskit.acquirers import Acquirer


@pytest.mark.parametrize(
    ("nns", "name", "organization"),
    [
        ("93600914", "GoPay", "PT Dompet Anak Bangsa"),
        ("93600915", "DANA", "PT Espay Debit Indonesia Koe"),
        ("93600912", "OVO", "PT Visionet Internasional"),
        ("93600918", "ShopeePay", "PT Airpay International Indonesia"),
        ("93600911", "LinkAja", "PT Fintek Karya Nusantara"),
        ("93600014", "BCA", "PT Bank Central Asia, Tbk"),
        ("93600002", "BRI", "PT Bank Rakyat Indonesia (Persero), Tbk"),
        ("93608161", "Pospay", "PT Pos Indonesia"),
    ],
)
def test_known_acquirers(nns: str, name: str, organization: str) -> None:
    acquirer = acquirers.lookup(nns)
    assert acquirer is not None
    assert acquirer.name == name
    assert acquirer.organization == organization
    assert str(acquirer) == name


def test_unknown_nns_is_none() -> None:
    assert acquirers.lookup("99999999") is None


def test_all_acquirers() -> None:
    everything = acquirers.all_acquirers()
    assert len(everything) == 128
    assert all(isinstance(a, Acquirer) for a in everything)


def test_data_file_is_clean() -> None:
    raw = resources.files("qriskit").joinpath("data").joinpath("nns.json").read_text("utf-8")
    data = json.loads(raw)
    assert data["url"].startswith("https://bicara131.bi.go.id/")
    nns_codes = [entry["nns"] for entry in data["entries"]]
    assert len(nns_codes) == len(set(nns_codes))
    for entry in data["entries"]:
        assert len(entry["nns"]) == 8 and entry["nns"].isdigit()
        assert entry["name"] and entry["organization"]
        for field in ("organization", "product"):
            text = entry[field] or ""
            assert text.count("(") == text.count(")"), entry
            assert "ArtaJasa" not in text and chr(0xFFFD) not in text, entry
