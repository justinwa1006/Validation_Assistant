import subprocess
import sys
from pathlib import Path


def test_package_import_is_headless_safe():
    root = Path(__file__).resolve().parent.parent
    code = f"import {root.name} as p; print(p.__all__)"
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=root.parent, text=True,
        capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ValidationAssistant" in completed.stdout
