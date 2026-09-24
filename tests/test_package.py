from __future__ import annotations

from importlib import metadata

import qris


def test_version() -> None:
    assert qris.__version__ == "0.1.0"
    assert metadata.version("qris") == qris.__version__


def test_no_runtime_dependencies() -> None:
    requirements = metadata.requires("qris") or []
    assert all("extra ==" in requirement for requirement in requirements)
