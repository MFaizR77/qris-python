from __future__ import annotations

from importlib import metadata

import qriskit


def test_version() -> None:
    assert qriskit.__version__ == "0.1.0"
    assert metadata.version("qriskit") == qriskit.__version__


def test_no_runtime_dependencies() -> None:
    requirements = metadata.requires("qriskit") or []
    assert all("extra ==" in requirement for requirement in requirements)
