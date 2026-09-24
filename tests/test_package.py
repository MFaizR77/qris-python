from __future__ import annotations

from importlib import metadata

import qriskit


def test_version() -> None:
    assert qriskit.__version__ == "0.2.0"
    assert metadata.version("qriskit") == qriskit.__version__


def test_no_runtime_dependencies() -> None:
    requirements = metadata.requires("qriskit") or []
    assert all("extra ==" in requirement for requirement in requirements)


def test_import_does_not_load_optional_dependencies() -> None:
    import subprocess
    import sys

    code = (
        "import sys, qriskit; "
        "print(sorted(m for m in ('segno', 'zxingcpp', 'PIL') if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
