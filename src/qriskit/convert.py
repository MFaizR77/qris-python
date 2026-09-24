"""Functions that return changed copies of a QRIS. Every result has a fresh CRC."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from . import spec, tlv
from ._money import format_amount
from .errors import QRISValidationError
from .model import QRIS, MerchantAccount, Tip, children_of, seal
from .tlv import MAX_VALUE_LENGTH, Node, is_two_digits
from .validate import crc_issues, validate

if TYPE_CHECKING:
    from .model import AmountLike

_MANAGED = frozenset({spec.TAG_PFI, spec.TAG_CRC})
_MAX_REFERENCE = spec.ADDITIONAL_DATA_RULES[spec.SUB_REFERENCE].max_len


def _node(tag: str, value: str) -> Node:
    if not isinstance(value, str):
        raise TypeError(f"Value for tag {tag} must be str, not {type(value).__name__}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"Value for tag {tag} cannot be encoded as UTF-8") from exc
    if len(value) > MAX_VALUE_LENGTH:
        raise ValueError(
            f"Value for tag {tag} is {len(value)} characters; the maximum is {MAX_VALUE_LENGTH}"
        )
    return Node(tag, value)


def _insert_sorted(nodes: list[Node], node: Node, *, root: bool) -> None:
    """Insert keeping ascending tag order. At root level 00 stays first and 63 last."""
    for index, existing in enumerate(nodes):
        if root and existing.tag == spec.TAG_CRC:
            nodes.insert(index, node)
            return
        if not (root and existing.tag == spec.TAG_PFI) and existing.tag > node.tag:
            nodes.insert(index, node)
            return
    nodes.append(node)


def _set(nodes: Sequence[Node], node: Node, *, root: bool) -> list[Node]:
    """Replace the first node with the same tag in place, or insert it in order."""
    result = list(nodes)
    for index, existing in enumerate(result):
        if existing.tag == node.tag:
            result[index] = node
            return result
    _insert_sorted(result, node, root=root)
    return result


def _split_path(path: str) -> tuple[str, str | None]:
    tag, dot, sub = path.partition(".")
    if not is_two_digits(tag) or (dot and not is_two_digits(sub)):
        raise ValueError(f"Invalid tag path {path!r}; use 'NN' or 'NN.NN', e.g. '59' or '62.05'")
    if tag in _MANAGED:
        raise ValueError(f"Tag {tag} is managed by the library and cannot be changed")
    if dot and not spec.is_template(tag):
        raise ValueError(f"Tag {tag} is not a template, so {path!r} has no sub-tags")
    return tag, (sub if dot else None)


def _template_children(qris: QRIS, tag: str) -> tuple[Node, ...]:
    value = qris.get(tag)
    if value is None:
        return ()
    children = children_of(value)
    if children is None:
        raise ValueError(f"Template {tag} is malformed, so its sub-tags cannot be changed")
    return children


def _require_intact_crc(qris: QRIS) -> None:
    problems = [i for i in crc_issues(qris) if i.code in ("crc.missing", "crc.mismatch")]
    if problems:
        raise QRISValidationError(problems)


def with_tag(qris: QRIS, path: str, value: str) -> QRIS:
    """Return a copy with ``path`` (``"59"`` or ``"62.05"``) set to ``value``.

    A missing parent template is created. Tags 00 and 63 cannot be set.
    """
    tag, sub = _split_path(path)
    if sub is None:
        return seal(_set(qris.nodes, _node(tag, value), root=True))
    children = _set(_template_children(qris, tag), _node(sub, value), root=False)
    parent = _node(tag, tlv.encode(children))
    return seal(_set(qris.nodes, parent, root=True))


def without_tag(qris: QRIS, path: str) -> QRIS:
    """Return a copy without ``path``. An emptied template is removed too."""
    tag, sub = _split_path(path)
    if sub is None:
        return seal([node for node in qris.nodes if node.tag != tag])
    if qris.get(tag) is None:
        return seal(qris.nodes)
    children = [child for child in _template_children(qris, tag) if child.tag != sub]
    if not children:
        return seal([node for node in qris.nodes if node.tag != tag])
    return seal(_set(qris.nodes, Node(tag, tlv.encode(children)), root=True))


def to_dynamic(
    qris: QRIS, amount: AmountLike, *, tip: Tip | None = None, reference: str | None = None
) -> QRIS:
    """Return a dynamic copy carrying ``amount``.

    Raises :class:`QRISValidationError` if the source CRC is missing or wrong,
    because recomputing it would hide a corrupted payload.
    """
    _require_intact_crc(qris)
    amount_text = format_amount(amount)
    if tip is not None and not isinstance(tip, Tip):
        raise TypeError(f"tip must be a qriskit.Tip, not {type(tip).__name__}")
    if reference is not None and not (
        isinstance(reference, str) and 0 < len(reference) <= _MAX_REFERENCE
    ):
        raise ValueError(f"reference must be a string of 1 to {_MAX_REFERENCE} characters")

    kept = [node for node in qris.nodes if node.tag not in spec.TRANSACTION_TAGS]
    nodes = _set(kept, Node(spec.TAG_POI, spec.POI_DYNAMIC), root=True)
    _insert_sorted(nodes, Node(spec.TAG_AMOUNT, amount_text), root=True)
    for node in tip.to_nodes() if tip else ():
        _insert_sorted(nodes, node, root=True)
    result = seal(nodes)
    if reference is not None:
        result = with_tag(result, f"{spec.TAG_ADDITIONAL}.{spec.SUB_REFERENCE}", reference)
    return result


def to_static(qris: QRIS) -> QRIS:
    """Return a static copy: tag 01 becomes 11 and tags 54-57 are removed."""
    _require_intact_crc(qris)
    kept = [node for node in qris.nodes if node.tag not in spec.TRANSACTION_TAGS]
    return seal(_set(kept, Node(spec.TAG_POI, spec.POI_STATIC), root=True))


def build(
    *,
    merchant_name: str,
    merchant_city: str,
    mcc: str,
    accounts: Sequence[MerchantAccount],
    postal_code: str | None = None,
    amount: AmountLike | None = None,
    tip: Tip | None = None,
    additional_data: Mapping[str, str] | None = None,
    currency: str = spec.CURRENCY_IDR,
    country: str = spec.COUNTRY_ID,
) -> QRIS:
    """Create a QRIS from scratch, for tests, sandboxes and demos.

    A payable QRIS still needs a merchant registered with an acquirer. Raises
    :class:`QRISValidationError` if the result would break any error-level rule.
    """
    if not accounts:
        raise ValueError("At least one merchant account is required")
    tags = [account.tag for account in accounts]
    if len(set(tags)) != len(tags):
        raise ValueError(f"Merchant account tags must be unique, got {tags}")

    nodes = [
        Node(spec.TAG_PFI, "01"),
        Node(spec.TAG_POI, spec.POI_STATIC if amount is None else spec.POI_DYNAMIC),
    ]
    nodes += [_node(a.tag, tlv.encode(a.nodes)) for a in sorted(accounts, key=lambda a: a.tag)]
    nodes += [_node(spec.TAG_MCC, mcc), _node(spec.TAG_CURRENCY, currency)]
    if amount is not None:
        nodes.append(Node(spec.TAG_AMOUNT, format_amount(amount)))
    if tip is not None:
        nodes += tip.to_nodes()
    nodes += [
        _node(spec.TAG_COUNTRY, country),
        _node(spec.TAG_NAME, merchant_name),
        _node(spec.TAG_CITY, merchant_city),
    ]
    if postal_code is not None:
        nodes.append(_node(spec.TAG_POSTAL, postal_code))
    if additional_data:
        children = sorted(
            (_node(sub, value) for sub, value in additional_data.items()), key=lambda node: node.tag
        )
        nodes.append(_node(spec.TAG_ADDITIONAL, tlv.encode(children)))

    result = seal(nodes)
    errors = [issue for issue in validate(result) if issue.severity == "error"]
    if errors:
        raise QRISValidationError(errors)
    return result
