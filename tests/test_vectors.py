"""Runs every file in tests/vectors. Adding a vector needs no code change."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import qriskit

VECTORS = sorted((Path(__file__).parent / "vectors").glob("*.json"))


def _actual(q: qriskit.QRIS, field: str) -> Any:
    tip = q.tip
    first = q.merchant_accounts[0] if q.merchant_accounts else None
    special = {
        "acquirer": lambda: first.acquirer.name if first and first.acquirer else None,
        "terminal_label": lambda: q.additional_data.terminal_label,
        "reference_label": lambda: q.additional_data.reference_label,
        "tip_kind": lambda: tip.kind if tip else None,
        "tip_value": lambda: str(tip.value) if tip and tip.value is not None else None,
        "amount": lambda: str(q.amount) if q.amount is not None else None,
    }
    return special[field]() if field in special else getattr(q, field)


def test_vectors_exist() -> None:
    assert len(VECTORS) >= 6


@pytest.mark.parametrize("path", VECTORS, ids=[p.stem for p in VECTORS])
def test_vector(path: Path) -> None:
    vector = json.loads(path.read_text(encoding="utf-8"))
    assert vector["source"] in ("emvco-spec", "synthetic", "real-anonymized")
    q = qriskit.parse(vector["payload"])
    for field, expected in vector["expect"].items():
        assert _actual(q, field) == expected, field
    assert sorted(i.code for i in qriskit.validate(q)) == sorted(vector["issues"])
    if not any(code.startswith("crc.") for code in vector["issues"]):
        assert q.dumps() == vector["payload"]
