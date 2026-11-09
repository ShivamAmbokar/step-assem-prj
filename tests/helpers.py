"""Shared test helpers: repo paths, tool loading, temporary projects for run_task tests."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"


def load_tool(name: str):
    """Import ``tools/<name>.py`` by path (``tools/`` is not a package)."""
    path = TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_tool_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def module_version(module_name: str) -> str | None:
    """Installed version of the distribution that provides ``module_name`` (or its __version__)."""
    top = module_name.split(".")[0]
    for dist in importlib.metadata.packages_distributions().get(top, []):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    try:
        return importlib.metadata.version(top)
    except importlib.metadata.PackageNotFoundError:
        pass
    try:
        value = getattr(importlib.import_module(top), "__version__", None)
    except Exception:
        return None
    return str(value) if value else None


def fixtures_content_hash(fixtures_dir: Path) -> str:
    """SHA-256 over the relative paths and bytes of ``fixtures/`` (``out/`` excluded)."""
    digest = hashlib.sha256()
    if not fixtures_dir.is_dir():
        return digest.hexdigest()
    for path in sorted(p for p in fixtures_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(fixtures_dir)
        if rel.parts[0] == "out" or "__pycache__" in rel.parts:
            continue
        digest.update(rel.as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def make_temp_project(
    root: Path,
    files: dict[str, str],
    tests: list[str] | None = None,
    commands: list[str] | None = None,
    artifacts: list[str] | None = None,
    allow_skip: bool = False,
) -> Path:
    """Create a minimal project with a fake manifest: agent task ``T1`` then human task ``HX``."""
    tasks = {
        "T1": {
            "kind": "agent", "step": "S99", "gates": "G99.1", "test_file": "tests/test_t1.py",
            "tests": ["test_ok"] if tests is None else tests,
            "commands": commands or [], "artifacts": artifacts or [],
            "allow_skip": allow_skip, "real": False, "tag": None, "next": "HX",
        },
        "HX": {"kind": "human", "verify_h": None, "next": "DONE"},
    }
    manifest = {"order": ["T1", "HX"], "tasks": tasks}
    (root / "plan" / "TASKS").mkdir(parents=True)
    (root / "plan" / "TASKS" / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (root / "plan" / "TASKS" / "INDEX.md").write_text(
        "# Task index\n\n| Done | ID | Kind | Step | Gate(s) | Title |\n|---|---|---|---|---|---|\n"
        "| [ ] | [T1](T1.md) | agent | S99 | G99.1 | Temp task |\n"
        "| [ ] | [HX](HX.md) | human | — | HX | Temp human |\n",
        encoding="utf-8",
    )
    (root / "plan" / "STATE.md").write_text(
        "# STATE\ncurrent_task: T1\nstatus: READY          # READY | AWAITING_REPORT | FAILING\n"
        "last_completed: none\nlast_report: none\nblocker: none\nnotes: none\n",
        encoding="utf-8",
    )
    (root / "PROGRESS.md").write_text("# PROGRESS\n", encoding="utf-8")
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def run_task_cli(root: Path, task_id: str, *flags: str) -> subprocess.CompletedProcess:
    """Run ``tools/run_task.py`` of this repo against the project at ``root``."""
    cmd = [sys.executable, str(TOOLS_DIR / "run_task.py"), "--root", str(root), task_id, *flags]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)
