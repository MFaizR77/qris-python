"""Exceptions, warnings and validation issues used across :mod:`qriskit`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]
ScanReason = Literal["no_qr", "no_qris", "multiple_qris", "unreadable_image", "image_too_large"]


@dataclass(frozen=True)
class Issue:
    """One problem reported by :func:`qriskit.validate`.

    ``code`` is stable across minor versions, so callers can branch on it.
    """

    code: str
    severity: Severity
    path: str | None
    message: str

    def __str__(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"{self.severity}: {self.code}{where}: {self.message}"


class QRISError(Exception):
    """Base class for every exception raised by this package."""


class QRISParseError(QRISError, ValueError):
    """The payload is not readable tag-length-value data."""

    def __init__(self, message: str, position: int | None = None) -> None:
        self.position = position
        super().__init__(message if position is None else f"{message} (at position {position})")


class QRISValidationError(QRISError, ValueError):
    """The payload is readable but breaks QRIS rules. ``issues`` lists every problem."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        shown = [i for i in self.issues if i.severity == "error"] or list(self.issues)
        super().__init__("; ".join(f"{i.code}: {i.message}" for i in shown))


class QRISScanError(QRISError, ValueError):
    """An image could not be turned into exactly one QRIS. ``reason`` says why."""

    def __init__(self, reason: ScanReason, message: str) -> None:
        self.reason: ScanReason = reason
        super().__init__(message)


class QRISWarning(UserWarning):
    """Something works but is not recommended, such as a QR image below the minimum size."""
