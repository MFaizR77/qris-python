"""Typed, immutable view of a QRIS payload.

The raw nodes are the single source of truth. Every typed attribute is a
read-only property computed from them, so ``parse(s).dumps() == s`` holds for
any valid payload and unknown tags are never lost.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from . import spec, tlv
from ._money import MAX_PERCENT, format_amount, format_percent, parse_decimal
from .acquirers import Acquirer, lookup
from .crc import crc16
from .errors import QRISParseError
from .tlv import Node

if TYPE_CHECKING:
    from typing import Union

    AmountLike = Union[int, str, Decimal]

# Whitespace, no-break space and byte-order mark, as left by copy-paste.
_STRIP = " \t\r\n\v\f" + chr(0xA0) + chr(0xFEFF)

TipKind = Literal["prompt", "fixed", "percent"]

_ADDITIONAL_FIELDS = {
    "01": "bill_number",
    "02": "mobile_number",
    "03": "store_label",
    "04": "loyalty_number",
    "05": "reference_label",
    "06": "customer_label",
    "07": "terminal_label",
    "08": "purpose",
    "09": "consumer_data_request",
    "10": "merchant_tax_id",
    "11": "merchant_channel",
}


def find(nodes: Sequence[Node], tag: str) -> str | None:
    """Value of the first node with ``tag``, or ``None``."""
    for node in nodes:
        if node.tag == tag:
            return node.value
    return None


def children_of(value: str) -> tuple[Node, ...] | None:
    """Decode a template value; ``None`` if it is not valid TLV."""
    try:
        return tlv.decode(value)
    except QRISParseError:
        return None


def seal(nodes: Sequence[Node]) -> QRIS:
    """Build a QRIS from ``nodes`` with a freshly computed CRC as the last node."""
    body = [node for node in nodes if node.tag != spec.TAG_CRC]
    checksum = crc16(tlv.encode(body) + spec.TAG_CRC + "04")
    return QRIS((*body, Node(spec.TAG_CRC, checksum)))


@dataclass(frozen=True)
class MerchantAccount:
    """One merchant account template (tags 26-51)."""

    tag: str
    nodes: tuple[Node, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        tag: str,
        guid: str,
        pan: str | None = None,
        merchant_id: str | None = None,
        criteria: str | None = None,
    ) -> MerchantAccount:
        """Build an account to pass to :func:`qriskit.build`."""
        if not spec.is_merchant_account_template(tag):
            raise ValueError(f"Merchant account tag must be between 26 and 51, got {tag!r}")
        pairs = (("00", guid), ("01", pan), ("02", merchant_id), ("03", criteria))
        return cls(tag, tuple(Node(sub, value) for sub, value in pairs if value is not None))

    @classmethod
    def national(cls, *, nmid: str, criteria: str | None = None) -> MerchantAccount:
        """The national repository account (tag 51) that carries the NMID."""
        return cls.create(
            tag=spec.TAG_NATIONAL, guid=spec.NATIONAL_GUID, merchant_id=nmid, criteria=criteria
        )

    def get(self, sub: str) -> str | None:
        return find(self.nodes, sub)

    @property
    def guid(self) -> str | None:
        return self.get("00")

    @property
    def pan(self) -> str | None:
        return self.get("01")

    @property
    def merchant_id(self) -> str | None:
        return self.get("02")

    @property
    def criteria(self) -> str | None:
        return self.get("03")

    @property
    def nns(self) -> str | None:
        """First 8 digits of the PAN: the acquirer's NNS code."""
        pan = self.pan
        if pan is None or len(pan) < 8:
            return None
        head = pan[:8]
        return head if head.isascii() and head.isdigit() else None

    @property
    def acquirer(self) -> Acquirer | None:
        nns = self.nns
        return lookup(nns) if nns else None

    @property
    def is_national(self) -> bool:
        return self.tag == spec.TAG_NATIONAL


@dataclass(frozen=True)
class AdditionalData:
    """Additional Data Field Template (tag 62). Empty when the tag is absent."""

    nodes: tuple[Node, ...] = ()

    def get(self, sub: str) -> str | None:
        return find(self.nodes, sub)

    @property
    def bill_number(self) -> str | None:
        return self.get("01")

    @property
    def mobile_number(self) -> str | None:
        return self.get("02")

    @property
    def store_label(self) -> str | None:
        return self.get("03")

    @property
    def loyalty_number(self) -> str | None:
        return self.get("04")

    @property
    def reference_label(self) -> str | None:
        return self.get("05")

    @property
    def customer_label(self) -> str | None:
        return self.get("06")

    @property
    def terminal_label(self) -> str | None:
        """The terminal ID (TID) printed on QRIS stickers."""
        return self.get("07")

    @property
    def purpose(self) -> str | None:
        return self.get("08")

    @property
    def consumer_data_request(self) -> str | None:
        return self.get("09")

    @property
    def merchant_tax_id(self) -> str | None:
        return self.get("10")

    @property
    def merchant_channel(self) -> str | None:
        return self.get("11")

    def to_dict(self) -> dict[str, str]:
        return {_ADDITIONAL_FIELDS.get(n.tag, n.tag): n.value for n in self.nodes}


@dataclass(frozen=True)
class Tip:
    """Tip or convenience fee (tags 55-57)."""

    kind: TipKind
    value: Decimal | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("prompt", "fixed", "percent"):
            raise ValueError(f"Tip kind must be 'prompt', 'fixed' or 'percent', got {self.kind!r}")
        if (self.kind == "prompt") != (self.value is None):
            raise ValueError("A prompt tip has no value; fixed and percent tips need one")

    @classmethod
    def prompt(cls) -> Tip:
        """The payer is asked to enter a tip."""
        return cls("prompt")

    @classmethod
    def fixed(cls, amount: AmountLike) -> Tip:
        """A fixed convenience fee, e.g. ``Tip.fixed(1000)``."""
        return cls("fixed", Decimal(format_amount(amount, field="fee")))

    @classmethod
    def percent(cls, rate: AmountLike) -> Tip:
        """A percentage convenience fee between 0.01 and 99.99, e.g. ``Tip.percent("2.5")``."""
        return cls("percent", Decimal(format_percent(rate)))

    def to_nodes(self) -> tuple[Node, ...]:
        if self.kind == "prompt":
            return (Node(spec.TAG_TIP, spec.TIP_PROMPT),)
        if self.kind == "fixed":
            return (
                Node(spec.TAG_TIP, spec.TIP_FIXED),
                Node(spec.TAG_FEE_FIXED, format_amount(self.value, field="fee")),
            )
        return (
            Node(spec.TAG_TIP, spec.TIP_PERCENT),
            Node(spec.TAG_FEE_PERCENT, format_percent(self.value)),
        )


@dataclass(frozen=True, repr=False)
class QRIS:
    """A parsed QRIS payload. Immutable: every change returns a new object."""

    nodes: tuple[Node, ...]

    def __repr__(self) -> str:
        return f"QRIS({self.dumps()!r})"

    def __str__(self) -> str:
        return self.dumps()

    def get(self, path: str) -> str | None:
        """Raw value at ``path``: ``"59"`` for a root tag, ``"62.05"`` for a sub-tag."""
        tag, _, sub = path.partition(".")
        value = find(self.nodes, tag)
        if not sub or value is None:
            return value
        children = children_of(value)
        return find(children, sub) if children is not None else None

    @property
    def version(self) -> str | None:
        return self.get(spec.TAG_PFI)

    @property
    def point_of_initiation(self) -> Literal["static", "dynamic"] | None:
        value = self.get(spec.TAG_POI)
        if value == spec.POI_STATIC:
            return "static"
        if value == spec.POI_DYNAMIC:
            return "dynamic"
        return None

    @property
    def is_static(self) -> bool:
        return self.point_of_initiation == "static"

    @property
    def is_dynamic(self) -> bool:
        return self.point_of_initiation == "dynamic"

    @property
    def merchant_accounts(self) -> tuple[MerchantAccount, ...]:
        return tuple(
            MerchantAccount(node.tag, children_of(node.value) or ())
            for node in self.nodes
            if spec.is_merchant_account_template(node.tag)
        )

    @property
    def national(self) -> MerchantAccount | None:
        return next((a for a in self.merchant_accounts if a.is_national), None)

    @property
    def nmid(self) -> str | None:
        national = self.national
        return national.merchant_id if national else None

    @property
    def mcc(self) -> str | None:
        return self.get(spec.TAG_MCC)

    @property
    def currency(self) -> str | None:
        return self.get(spec.TAG_CURRENCY)

    @property
    def amount(self) -> Decimal | None:
        return parse_decimal(self.get(spec.TAG_AMOUNT))

    @property
    def tip(self) -> Tip | None:
        indicator = self.get(spec.TAG_TIP)
        if indicator == spec.TIP_PROMPT:
            return Tip.prompt()
        if indicator == spec.TIP_FIXED:
            fee = parse_decimal(self.get(spec.TAG_FEE_FIXED))
            return Tip("fixed", fee) if fee is not None else None
        if indicator == spec.TIP_PERCENT:
            rate = parse_decimal(self.get(spec.TAG_FEE_PERCENT))
            return Tip("percent", rate) if rate is not None and rate <= MAX_PERCENT else None
        return None

    @property
    def country(self) -> str | None:
        return self.get(spec.TAG_COUNTRY)

    @property
    def merchant_name(self) -> str | None:
        return self.get(spec.TAG_NAME)

    @property
    def merchant_city(self) -> str | None:
        return self.get(spec.TAG_CITY)

    @property
    def postal_code(self) -> str | None:
        return self.get(spec.TAG_POSTAL)

    @property
    def additional_data(self) -> AdditionalData:
        value = self.get(spec.TAG_ADDITIONAL)
        return AdditionalData(children_of(value) or ()) if value is not None else AdditionalData()

    @property
    def crc(self) -> str | None:
        """Tag 63 exactly as it appears in the payload (not recomputed)."""
        return self.get(spec.TAG_CRC)

    def dumps(self) -> str:
        """The payload text. The CRC is always recomputed."""
        return tlv.encode(seal(self.nodes).nodes)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serialisable summary."""
        tip = self.tip
        amount = self.amount
        return {
            "payload": self.dumps(),
            "version": self.version,
            "point_of_initiation": self.point_of_initiation,
            "merchant_name": self.merchant_name,
            "merchant_city": self.merchant_city,
            "postal_code": self.postal_code,
            "country": self.country,
            "mcc": self.mcc,
            "currency": self.currency,
            "amount": str(amount) if amount is not None else None,
            "tip": (
                {"kind": tip.kind, "value": None if tip.value is None else str(tip.value)}
                if tip
                else None
            ),
            "nmid": self.nmid,
            "merchant_accounts": [
                {
                    "tag": a.tag,
                    "guid": a.guid,
                    "pan": a.pan,
                    "merchant_id": a.merchant_id,
                    "criteria": a.criteria,
                    "nns": a.nns,
                    "acquirer": a.acquirer.name if a.acquirer else None,
                }
                for a in self.merchant_accounts
            ],
            "additional_data": self.additional_data.to_dict(),
            "crc": self.crc,
        }

    # Changes live in convert.py; these methods are shortcuts.

    def to_dynamic(
        self, amount: AmountLike, *, tip: Tip | None = None, reference: str | None = None
    ) -> QRIS:
        """Return a dynamic copy with ``amount`` (and optional tip and reference)."""
        from .convert import to_dynamic

        return to_dynamic(self, amount, tip=tip, reference=reference)

    def to_static(self) -> QRIS:
        """Return a static copy without amount or tip."""
        from .convert import to_static

        return to_static(self)

    def with_tag(self, path: str, value: str) -> QRIS:
        """Return a copy with ``path`` (``"59"`` or ``"62.05"``) set to ``value``."""
        from .convert import with_tag

        return with_tag(self, path, value)

    def without_tag(self, path: str) -> QRIS:
        """Return a copy without ``path``."""
        from .convert import without_tag

        return without_tag(self, path)


def parse_payload(payload: str) -> QRIS:
    """Read a payload without checking QRIS rules (see :func:`qriskit.parse`)."""
    if not isinstance(payload, str):
        raise TypeError(f"payload must be str, not {type(payload).__name__}")
    text = payload.strip(_STRIP)
    if not text:
        raise QRISParseError("Payload is empty")
    leading = len(payload) - len(payload.lstrip(_STRIP))
    return QRIS(tlv.decode(text, offset=leading))
