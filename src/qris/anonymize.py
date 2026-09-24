"""Replace merchant data with random look-alikes so a payload can be shared safely."""

from __future__ import annotations

import random
import string

from . import spec, tlv
from .model import QRIS, children_of, seal
from .tlv import Node

# Sub-tags kept as-is: GUID and criteria in merchant accounts, language code in tag 64.
_KEEP_IN_ACCOUNT = frozenset({"00", "03"})
_KEEP_IN_LANGUAGE = frozenset({"00"})
_MASKED_ROOT = frozenset({spec.TAG_NAME, spec.TAG_CITY, spec.TAG_POSTAL})


def anonymize(qris: QRIS, *, seed: int = 0) -> QRIS:
    """Return a copy with merchant data replaced and the structure unchanged.

    Masked: name, city, postal code, PAN digits after the NNS, merchant IDs,
    NMID (the ``ID`` prefix is kept), and every value in tags 62, 64 and 80-99.
    Kept: tag order, value lengths, GUIDs, NNS, MCC, criteria, amount and tip.
    The same ``seed`` always gives the same result.
    """
    rng = random.Random(seed)

    def mask(value: str, keep: int = 0) -> str:
        head, tail = value[:keep], value[keep:]
        return head + "".join(
            rng.choice(string.ascii_uppercase)
            if c.isalpha()
            else rng.choice(string.digits)
            if c.isdigit()
            else c
            for c in tail
        )

    def mask_children(value: str, keep: frozenset[str], prefix: dict[str, int]) -> str:
        children = children_of(value)
        if children is None:
            return mask(value)
        return tlv.encode(
            child
            if child.tag in keep
            else Node(child.tag, mask(child.value, prefix.get(child.tag, 0)))
            for child in children
        )

    nodes: list[Node] = []
    for node in qris.nodes:
        tag = node.tag
        if tag in _MASKED_ROOT:
            nodes.append(Node(tag, mask(node.value)))
        elif spec.is_merchant_account_template(tag):
            # PAN keeps its 8-digit NNS; the NMID in tag 51 keeps its "ID" prefix.
            prefix = {"01": 8, "02": 2 if tag == spec.TAG_NATIONAL else 0}
            nodes.append(Node(tag, mask_children(node.value, _KEEP_IN_ACCOUNT, prefix)))
        elif tag == spec.TAG_LANGUAGE:
            nodes.append(Node(tag, mask_children(node.value, _KEEP_IN_LANGUAGE, {})))
        elif spec.is_template(tag):
            nodes.append(Node(tag, mask_children(node.value, frozenset(), {})))
        else:
            nodes.append(node)
    return seal(nodes)
