"""Look up the acquirer (PJSP) of a merchant account from its NNS code.

The NNS is the 8-digit code issued by BSN to each QRIS acquirer. It is also the
first 8 digits of the Merchant PAN. Data comes from Bank Indonesia's public list;
see ``data/nns.json`` for the source and retrieval date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources


@dataclass(frozen=True)
class Acquirer:
    nns: str
    name: str
    organization: str
    product: str | None

    def __str__(self) -> str:
        return self.name


@cache
def _table() -> dict[str, Acquirer]:
    data = resources.files("qriskit").joinpath("data").joinpath("nns.json")
    entries = json.loads(data.read_text(encoding="utf-8"))["entries"]
    return {
        e["nns"]: Acquirer(e["nns"], e["name"], e["organization"], e["product"]) for e in entries
    }


def lookup(nns: str) -> Acquirer | None:
    """Return the acquirer for an 8-digit NNS, or ``None`` if it is not in the list."""
    return _table().get(nns)


def all_acquirers() -> tuple[Acquirer, ...]:
    """Every known acquirer, sorted by NNS."""
    return tuple(_table().values())
