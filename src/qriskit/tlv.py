"""Generic EMVCo tag-length-value encoding. This module knows nothing about QRIS."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .errors import QRISParseError

MAX_VALUE_LENGTH = 99


def is_two_digits(text: str) -> bool:
    """True if ``text`` is exactly two ASCII digits, like ``"05"``."""
    return len(text) == 2 and text.isascii() and text.isdigit()


@dataclass(frozen=True)
class Node:
    """One TLV element. ``value`` is kept verbatim; a template's value is nested TLV text."""

    tag: str
    value: str

    def __post_init__(self) -> None:
        if not is_two_digits(self.tag):
            raise ValueError(f"Tag must be two digits, got {self.tag!r}")

    def encode(self) -> str:
        if len(self.value) > MAX_VALUE_LENGTH:
            raise ValueError(
                f"Value of tag {self.tag} is {len(self.value)} characters long; "
                f"the maximum is {MAX_VALUE_LENGTH}"
            )
        return f"{self.tag}{len(self.value):02d}{self.value}"


def decode(data: str, *, offset: int = 0) -> tuple[Node, ...]:
    """Split ``data`` into nodes. Lengths count characters, not bytes.

    ``offset`` is added to positions in error messages, so errors inside a
    nested template point at the right place in the whole payload.
    """
    nodes: list[Node] = []
    pos = 0
    end_of_data = len(data)
    while pos < end_of_data:
        if pos + 4 > end_of_data:
            raise QRISParseError(f"Truncated element {data[pos:]!r}", offset + pos)
        tag = data[pos : pos + 2]
        length_text = data[pos + 2 : pos + 4]
        if not is_two_digits(tag):
            raise QRISParseError(f"Invalid tag {tag!r}", offset + pos)
        if not is_two_digits(length_text):
            raise QRISParseError(f"Invalid length {length_text!r} for tag {tag}", offset + pos + 2)
        start = pos + 4
        end = start + int(length_text)
        if end > end_of_data:
            raise QRISParseError(
                f"Tag {tag} declares {int(length_text)} characters "
                f"but only {end_of_data - start} remain",
                offset + start,
            )
        nodes.append(Node(tag, data[start:end]))
        pos = end
    return tuple(nodes)


def encode(nodes: Iterable[Node]) -> str:
    """Join nodes back into TLV text."""
    return "".join(node.encode() for node in nodes)
