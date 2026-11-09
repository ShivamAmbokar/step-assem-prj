#!/usr/bin/env python3
"""Quick local check (HANDBOOK 7): ``ruff check .`` + ``pytest -m "not real and not slow"``.

    python tools/check.py

``occ`` tests run when OCP is importable and are skipped otherwise (see tests/conftest.py).
Exit code 0 only when both steps succeed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ruff_command() -> list[str]:
    exe = shutil.which("ruff")
    return [exe] if exe else [sys.executable, "-m", "ruff"]


def main() -> int:
    steps = [
        ("ruff check .", _ruff_command() + ["check", "."]),
        ("pytest", [sys.executable, "-m", "pytest", "-m", "not real and not slow", "-q"]),
    ]
    failed = []
    for label, cmd in steps:
        print(f"== {label}", flush=True)
        try:
            code = subprocess.run(cmd, cwd=ROOT).returncode
        except OSError as exc:
            print(f"cannot run {label}: {exc}")
            code = 127
        if code != 0:
            failed.append(label)
    print("check: " + ("OK" if not failed else "FAILED (" + ", ".join(failed) + ")"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
