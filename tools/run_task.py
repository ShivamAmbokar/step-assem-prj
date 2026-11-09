#!/usr/bin/env python3
"""Run one task card's gate: tests + regression + commands + artifacts -> report -> verdict.

    python tools/run_task.py <ID> [--no-regress] [--keep-state] [--root DIR]

Protocol: HANDBOOK 0.2 and Appendix I. Steps, in order:

1. read ``plan/TASKS/manifest.json`` (validated) for ``<ID>``;
2. run the task's tests (``pytest --json-report``), then the regression suite
   (``pytest -m "not real and not slow"``, i.e. every earlier task as well);
3. run the task's ``commands`` and check its required ``artifacts``;
4. write ``reports/<ID>/report.json`` + ``report.md``, copy artifacts into ``reports/<ID>/`` and zip
   everything to ``reports/<ID>.zip`` (``reports/<ID>/`` is wiped first: no stale files);
5. verdict **PASS** iff all task tests passed (none skipped unless ``allow_skip``), the regression
   suite passed, every command exited 0 and every artifact exists;
6. bookkeeping: PASS -> ``plan/STATE.md`` (``current_task`` = next, ``status: READY``), tick
   ``plan/TASKS/INDEX.md``, append to ``PROGRESS.md``; FAIL -> ``status: FAILING`` and
   ``last_report``.

``--keep-state`` leaves STATE/INDEX/PROGRESS untouched. ``--no-regress`` skips the regression suite
(quick iteration only); it implies ``--keep-state`` because a task cannot be accepted without it.

Exit code: 0 PASS, 1 FAIL, 2 usage / manifest problem. Standard library only (+ pytest and
pytest-json-report in the interpreter that runs this script).
"""
from __future__ import annotations

import argparse
import ast
import datetime
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

REGRESSION_MARKEXPR = "not real and not slow"
TAIL_LINES = 30
TAIL_CHARS = 4000
PACKAGES = {  # report key -> importable top-level module
    "cadquery": "cadquery",
    "OCP": "OCP",
    "numpy": "numpy",
    "scipy": "scipy",
    "trimesh": "trimesh",
    "pyvista": "pyvista",
    "pytest": "pytest",
    "pytest-json-report": "pytest_jsonreport",
}
_AGENT_TYPES = {
    "step": str, "gates": str, "test_file": str, "tests": list, "commands": list,
    "artifacts": list, "allow_skip": bool, "real": bool, "next": str,
}


# ------------------------------------------------------------------------------ manifest


def validate_manifest(manifest: object) -> list[str]:
    """Return a list of problems with a manifest (empty when valid)."""
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    order, tasks = manifest.get("order"), manifest.get("tasks")
    errors: list[str] = []
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        errors.append("'order' must be a list of task ids")
    if not isinstance(tasks, dict):
        errors.append("'tasks' must be an object keyed by task id")
    if errors:
        return errors
    if len(set(order)) != len(order):
        errors.append("'order' contains duplicate ids")
    for tid in sorted(set(order) ^ set(tasks)):
        errors.append(f"{tid}: present in only one of 'order' / 'tasks'")
    for i, tid in enumerate(order):
        task = tasks.get(tid)
        if task is None:
            continue
        errors.extend(_validate_task(tid, task))
        expected = order[i + 1] if i + 1 < len(order) else "DONE"
        if isinstance(task, dict) and task.get("next") != expected:
            errors.append(f"{tid}: next={task.get('next')!r}, expected {expected!r} (order)")
    return errors


def _validate_task(tid: str, task: object) -> list[str]:
    if not isinstance(task, dict):
        return [f"{tid}: entry must be an object"]
    kind = task.get("kind")
    if kind == "human":
        errors = []
        if task.get("verify_h") is not None and not isinstance(task.get("verify_h"), str):
            errors.append(f"{tid}: verify_h must be null or a string")
        if not isinstance(task.get("next"), str):
            errors.append(f"{tid}: next must be a string")
        return errors
    if kind != "agent":
        return [f"{tid}: kind must be 'agent' or 'human', got {kind!r}"]
    errors = [
        f"{tid}: field {key!r} must be {typ.__name__}"
        for key, typ in _AGENT_TYPES.items()
        if not isinstance(task.get(key), typ)
    ]
    if task.get("tag") is not None and not isinstance(task.get("tag"), str):
        errors.append(f"{tid}: tag must be null or a string")
    for key in ("tests", "commands", "artifacts"):
        value = task.get(key)
        if isinstance(value, list) and not all(isinstance(x, str) for x in value):
            errors.append(f"{tid}: {key} must be a list of strings")
    return errors


def load_manifest(root: Path) -> dict:
    """Load and validate ``plan/TASKS/manifest.json``; raise ValueError when it is unusable."""
    path = root / "plan" / "TASKS" / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid manifest:\n  " + "\n  ".join(errors))
    return manifest


# ------------------------------------------------------------------------------ environment


def _distribution_version(module: str) -> str | None:
    for dist in importlib.metadata.packages_distributions().get(module, []):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    try:
        return importlib.metadata.version(module)
    except importlib.metadata.PackageNotFoundError:
        return None


def package_versions() -> dict[str, str | None]:
    return {name: _distribution_version(module) for name, module in PACKAGES.items()}


def _ram_gb() -> float | None:
    try:
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            return round(int(out.stdout.strip()) / 2**30, 1)
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (f"f{i}", ctypes.c_ulonglong) for i in range(7)
            ]

        mem = _Mem()
        mem.length = ctypes.sizeof(mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))  # type: ignore[attr-defined]
        return round(mem.f0 / 2**30, 1)
    except Exception:
        return None


def env_info() -> dict:
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": os.cpu_count(),
        "ram_gb": _ram_gb(),
        "packages": package_versions(),
    }


def _git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_info(root: Path) -> dict:
    status = _git(root, "status", "--porcelain", "--", ".", ":(exclude)reports")
    return {
        "sha": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


# ------------------------------------------------------------------------------ pytest


def gate_of(nodeid: str) -> str:
    """``tests/x.py::test_g10_2_foo`` -> ``G10.2`` (empty when the name has no gate)."""
    match = re.search(r"::test_g(\d+)_(\d+[a-z]?)_", nodeid)
    return f"G{int(match.group(1))}.{match.group(2)}" if match else ""


def resolve_node_ids(root: Path, test_file: str, names: list[str]) -> tuple[list[str], list[str]]:
    """Map manifest test names to pytest node ids; return (node_ids, names_not_found)."""
    path = root / test_file
    if not path.is_file():
        return [], list(names)
    found: dict[str, str] = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        found = {n: f"{test_file}::{n}" for n in names}  # let pytest report the collection error
        tree = ast.Module(body=[], type_ignores=[])
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, funcs):
            found.setdefault(node.name, f"{test_file}::{node.name}")
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, funcs):
                    found.setdefault(sub.name, f"{test_file}::{node.name}::{sub.name}")
    node_ids, missing = [], []
    for name in names:
        nodeid = name if ("::" in name or "/" in name) else found.get(name)
        (node_ids if nodeid else missing).append(nodeid or name)
    return node_ids, missing


def run_pytest(root: Path, args: list[str]) -> dict:
    """Run pytest with the JSON report plugin; return exit code, parsed report and output."""
    tmp = Path(tempfile.mkdtemp(prefix="run_task_"))
    json_path = tmp / "report.json"
    cmd = [sys.executable, "-m", "pytest", *args, "--rootdir", str(root), "-q",
           "--json-report", f"--json-report-file={json_path}"]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    report = None
    if json_path.is_file():
        try:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        except ValueError:
            report = None
    shutil.rmtree(tmp, ignore_errors=True)
    return {"exit": proc.returncode, "report": report, "output": proc.stdout + proc.stderr}


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])[-TAIL_CHARS:]


def _stage_message(stage: dict) -> str:
    crash = stage.get("crash") or {}
    if crash.get("message"):
        return str(crash["message"]).splitlines()[0]
    longrepr = stage.get("longrepr")
    if isinstance(longrepr, str) and longrepr.strip():
        text = longrepr.strip()
        if text.startswith("("):  # skip tuples: ('file', line, 'Skipped: reason')
            try:
                text = str(ast.literal_eval(text)[-1])
            except (ValueError, SyntaxError, IndexError, TypeError):
                pass
        return text.splitlines()[-1] if "\n" in text else text
    return ""


def parse_items(report: dict) -> list[dict]:
    """Convert pytest-json-report ``tests`` entries into report items."""
    items = []
    for test in report.get("tests", []):
        stages = [test.get(k) or {} for k in ("setup", "call", "teardown")]
        outcome = str(test.get("outcome", "error"))
        item = {
            "nodeid": str(test.get("nodeid", "")).replace("\\", "/"),
            "outcome": outcome,
            "duration_s": round(sum(float(s.get("duration") or 0) for s in stages), 3),
            "gate": gate_of(str(test.get("nodeid", ""))),
            "message": "",
        }
        if outcome != "passed":
            bad = next((s for s in stages if s.get("outcome") not in (None, "passed")), {})
            item["message"] = _stage_message(bad)
            item["traceback_tail"] = _tail(str(bad.get("longrepr") or ""))
        items.append(item)
    return items


def collector_failures(report: dict) -> list[dict]:
    """Modules that failed to import/collect (they do not show up in ``tests``)."""
    out = []
    for coll in report.get("collectors", []):
        if coll.get("outcome") == "failed":
            out.append({
                "nodeid": str(coll.get("nodeid", "")), "outcome": "error", "gate": "",
                "message": _stage_message(coll) or "collection error",
                "traceback_tail": _tail(str(coll.get("longrepr") or "")),
            })
    return out


def _counts(items: list[dict]) -> dict:
    return {
        "passed": sum(i["outcome"] == "passed" for i in items),
        "failed": sum(i["outcome"] not in ("passed", "skipped") for i in items),
        "skipped": sum(i["outcome"] == "skipped" for i in items),
        "duration_s": round(sum(i.get("duration_s", 0) for i in items), 2),
    }


def run_task_tests(root: Path, task: dict) -> dict:
    """Run the task's own tests; ``problems`` lists everything that stops it from passing."""
    node_ids, missing = resolve_node_ids(root, task["test_file"], task["tests"])
    problems = [f"test not found in {task['test_file']}: {name}" for name in missing]
    result = {"items": [], "node_ids": node_ids, "problems": problems, "notes": []}
    if node_ids:
        run = run_pytest(root, node_ids)
        report = run["report"]
        if report is None:
            result["notes"].append(
                f"pytest produced no JSON report (exit {run['exit']}); is pytest-json-report "
                f"installed (pip install -r requirements.txt)?\n{_tail(run['output'])}"
            )
        else:
            result["items"] = parse_items(report)
            result["collector_failures"] = collector_failures(report)
    for failure in result.get("collector_failures", []):
        problems.append(f"collection error {failure['nodeid']}: {failure['message']}")
    for nodeid in node_ids:
        if not _match_items(result["items"], nodeid):
            problems.append(f"test did not run: {nodeid}")
    for item in result["items"]:
        if item["outcome"] == "passed" or (item["outcome"] == "skipped" and task["allow_skip"]):
            continue
        problems.append(f"{item['nodeid']}: {item['outcome']} {item['message']}".rstrip())
    result.update(_counts(result["items"]))
    return result


def _match_items(items: list[dict], nodeid: str) -> list[dict]:
    return [i for i in items if i["nodeid"] == nodeid or i["nodeid"].startswith(nodeid + "[")]


def run_regression(root: Path) -> dict:
    """Run every earlier task's tests: ``pytest -m "not real and not slow"``."""
    args = ["-m", REGRESSION_MARKEXPR] + (["tests"] if (root / "tests").is_dir() else [])
    run = run_pytest(root, args)
    report = run["report"]
    result = {"passed": 0, "failed": 0, "skipped": 0, "duration_s": 0.0, "failures": [],
              "exit": run["exit"], "ok": run["exit"] in (0, 5)}
    if report is None:
        result["failed"] = 0 if result["ok"] else 1
        result["total"] = result["failed"]
        result["error"] = _tail(run["output"])
        return result
    items = parse_items(report)
    failures = [i for i in items if i["outcome"] not in ("passed", "skipped")]
    failures += collector_failures(report)
    result.update(_counts(items))
    result["failed"] += len(collector_failures(report))
    result["failures"] = [
        {k: f.get(k, "") for k in ("nodeid", "gate", "message", "traceback_tail")} for f in failures
    ]
    result["ok"] = result["ok"] and not failures
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    return result


# ------------------------------------------------------------------------------ commands, artifacts


def run_commands(root: Path, commands: list[str], artifacts: list[str]) -> list[dict]:
    """Run each manifest command (no shell; ``$VAR`` expanded; ``python`` = this interpreter)."""
    results = []
    for cmd in commands:
        start = time.time()
        tokens = [os.path.expandvars(t) for t in shlex.split(cmd)]
        if tokens and tokens[0] in ("python", "python3"):
            tokens[0] = sys.executable
        try:
            proc = subprocess.run(tokens, cwd=root, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            code, output = proc.returncode, proc.stdout + proc.stderr
        except (OSError, ValueError) as exc:
            code, output = 127, str(exc)
        files = [a for a in artifacts
                 if (root / a).exists() and (root / a).stat().st_mtime >= start - 2]
        results.append({"cmd": cmd, "exit": code, "stdout_tail": _tail(output), "files": files,
                        "duration_s": round(time.time() - start, 2)})
    return results


def _artifact_dest(task_id: str, rel: str) -> str | None:
    """Path of an artifact below ``reports/<ID>/`` (None when it already lives there)."""
    rel = Path(rel).as_posix()
    if rel.startswith(f"reports/{task_id}/"):
        return None
    return rel[len("reports/"):] if rel.startswith("reports/") else rel


def collect_artifacts(root: Path, task_id: str, artifacts: list[str], report_dir: Path):
    """Copy required artifacts into ``reports/<ID>/``; return (present, missing) as repo paths."""
    present, missing = [], []
    for rel in artifacts:
        src = root / rel
        if Path(rel).is_absolute() or ".." in Path(rel).parts or not src.exists():
            missing.append(rel)
            continue
        dest_rel = _artifact_dest(task_id, rel)
        if dest_rel is None:
            present.append(Path(rel).as_posix())
            continue
        dest = report_dir / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
        present.append(f"reports/{task_id}/{dest_rel}")
    return present, missing


# ------------------------------------------------------------------------------ bookkeeping


def set_state_values(path: Path, updates: dict[str, str]) -> None:
    """Replace the value of ``key: value`` lines in STATE.md, keeping comments and other lines."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pending = dict(updates)
    for i, line in enumerate(lines):
        match = re.match(r"^([A-Za-z_]+)(:[ \t]*)(\S*)(.*?)(\r?\n)?$", line)
        if match and match.group(1) in pending:
            key = match.group(1)
            sep, rest, eol = match.group(2), match.group(4), match.group(5) or ""
            lines[i] = f"{key}{sep}{pending.pop(key)}{rest}{eol}"
            if not lines[i].endswith("\n"):
                lines[i] += "\n"
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines += [f"{key}: {value}\n" for key, value in pending.items()]
    path.write_text("".join(lines), encoding="utf-8")


def tick_index(path: Path, task_id: str) -> bool:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(
        rf"^\| \[ \]( \| \[{re.escape(task_id)}\])", r"| [x]\1", text, count=1, flags=re.M
    )
    if count:
        path.write_text(new, encoding="utf-8")
    return bool(count)


def append_progress(path: Path, line: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else "# PROGRESS\n"
    path.write_text(text + ("" if text.endswith("\n") else "\n") + line + "\n", encoding="utf-8")


def _ratio(counts: dict) -> str:
    """``passed/total`` of a task_tests / regression block."""
    return f"{counts['passed']}/{counts['passed'] + counts['failed'] + counts['skipped']}"


def update_bookkeeping(root: Path, task_id: str, task: dict, rep: dict) -> list[str]:
    """STATE / INDEX / PROGRESS after a run; returns notes about anything that went wrong."""
    notes = []
    tests, regress = rep["task_tests"], rep["regression"]
    sha = (rep["git"]["sha"] or "nogit")[:8]
    line = (f"{rep['timestamp'][:10]} {task_id} {rep['verdict']} "
            f"tests={_ratio(tests)} regress={_ratio(regress)} "
            f"sha={sha} report=reports/{task_id}/report.md")
    steps = []
    state = root / "plan" / "STATE.md"
    if rep["verdict"] == "PASS":
        updates = {"current_task": task["next"], "status": "READY", "last_completed": task_id,
                   "last_report": f"reports/{task_id}/report.md", "blocker": "none"}
        steps.append(("STATE.md", lambda: set_state_values(state, updates)))
        index = root / "plan" / "TASKS" / "INDEX.md"
        steps.append(("INDEX.md", lambda: tick_index(index, task_id)))
    else:
        updates = {"current_task": task_id, "status": "FAILING",
                   "last_report": f"reports/{task_id}.zip"}
        steps.append(("STATE.md", lambda: set_state_values(state, updates)))
    steps.append(("PROGRESS.md", lambda: append_progress(root / "PROGRESS.md", line)))
    for name, step in steps:
        try:
            step()
        except OSError as exc:
            notes.append(f"could not update {name}: {exc}")
    return notes


# ------------------------------------------------------------------------------ report output


def _words(counts: dict) -> str:
    return f"{counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped"


def render_markdown(rep: dict) -> str:
    """Readable report; failures come first."""
    t, r = rep["task_tests"], rep["regression"]
    out = [f"# {rep['task']} — {rep['verdict']}", "",
           f"- time: {rep['timestamp']}  git: {rep['git'].get('sha')} ({rep['git'].get('branch')})"
           f" dirty={rep['git'].get('dirty')}",
           f"- task tests: {t['passed']} passed, {t['failed']} failed, {t['skipped']} skipped",
           "- regression: " + ("skipped (--no-regress)" if r is None else _words(r)),
           "", "## Failures", ""]
    out += [f"- {reason}" for reason in rep["reasons"]] or ["None."]
    bad = [i for i in t["items"] if i["outcome"] not in ("passed", "skipped")]
    for item in bad + (r["failures"] if r else []):
        gate = f" ({item['gate']})" if item.get("gate") else ""
        out += ["", f"### {item['nodeid']}{gate}", "", f"{item.get('message', '')}", "",
                "```", item.get("traceback_tail", ""), "```"]
    for cmd in rep["commands"]:
        if cmd["exit"] != 0:
            out += ["", f"### command failed (exit {cmd['exit']}): `{cmd['cmd']}`", "",
                    "```", cmd["stdout_tail"], "```"]
    out += ["", "## Task tests", "", "| test | gate | outcome | s |", "|---|---|---|---|"]
    out += [f"| {i['nodeid']} | {i['gate']} | {i['outcome']} | {i['duration_s']} |"
            for i in t["items"]]
    out += ["", "## Commands", ""]
    out += [f"- `{c['cmd']}` -> exit {c['exit']} ({c['duration_s']} s) files: {c['files']}"
            for c in rep["commands"]] or ["None."]
    out += ["", "## Artifacts", ""] + ([f"- {a}" for a in rep["artifacts"]] or ["None."])
    out += ["", "## Environment", "", "```json", json.dumps(rep["env"], indent=1), "```"]
    out += ["", "## Notes", ""] + ([f"- {n}" for n in rep["notes"]] or ["None."]) + [""]
    return "\n".join(out)


def write_reports(root: Path, task_id: str, report_dir: Path, rep: dict) -> Path:
    (report_dir / "report.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    (report_dir / "report.md").write_text(render_markdown(rep), encoding="utf-8")
    zip_path = root / "reports" / f"{task_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in report_dir.rglob("*") if p.is_file()):
            zf.write(path, f"{task_id}/{path.relative_to(report_dir).as_posix()}")
    return zip_path


# ------------------------------------------------------------------------------ main flow


def _verdict(tests: dict, regress: dict | None, commands: list[dict], missing: list[str]):
    reasons = list(tests["problems"])
    if regress is not None and not regress["ok"]:
        reasons.append(
            f"regression suite failed ({regress['failed']} failing, pytest exit {regress['exit']})"
        )
    reasons += [f"command exited {c['exit']}: {c['cmd']}" for c in commands if c["exit"] != 0]
    reasons += [f"required artifact missing: {a}" for a in missing]
    return ("FAIL" if reasons else "PASS"), reasons


def run(task_id: str, root: Path, no_regress: bool = False, keep_state: bool = False) -> dict:
    """Run the full protocol for ``task_id``; returns the report dict (also written to disk)."""
    manifest = load_manifest(root)
    task = manifest["tasks"].get(task_id)
    if task is None:
        raise ValueError(f"unknown task id {task_id!r} (see plan/TASKS/manifest.json)")
    if task["kind"] != "agent":
        raise ValueError(f"{task_id} is a human task: run `python tools/verify_h.py {task_id}`")
    report_dir = root / "reports" / task_id
    shutil.rmtree(report_dir, ignore_errors=True)
    report_dir.mkdir(parents=True)
    git, notes = git_info(root), []
    if task["real"] and not os.environ.get("FITFINDER_DATA"):
        notes.append("FITFINDER_DATA is not set: tests marked 'real' will be skipped")
    print(f"[{task_id}] task tests ...", flush=True)
    tests = run_task_tests(root, task)
    notes += tests.pop("notes")
    regress = None
    if not no_regress:
        print(f"[{task_id}] regression suite ...", flush=True)
        regress = run_regression(root)
    print(f"[{task_id}] commands / artifacts ...", flush=True)
    commands = run_commands(root, task["commands"], task["artifacts"])
    present, missing = collect_artifacts(root, task_id, task["artifacts"], report_dir)
    verdict, reasons = _verdict(tests, regress, commands, missing)
    rep = {
        "task": task_id, "verdict": verdict,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": git, "env": env_info(),
        "task_tests": {k: tests[k] for k in ("passed", "failed", "skipped", "duration_s", "items")},
        "regression": regress, "commands": commands, "artifacts": present,
        "reasons": reasons, "notes": notes,
    }
    state = _read_state_value(root, "current_task")
    if state not in (None, task_id):
        notes.append(f"plan/STATE.md says current_task={state}, ran {task_id}")
    if no_regress or keep_state:
        notes.append("bookkeeping skipped (" + ("--no-regress" if no_regress else "--keep-state")
                     + "): STATE.md, INDEX.md and PROGRESS.md are unchanged")
    else:
        notes += update_bookkeeping(root, task_id, task, rep)
    rep["zip"] = f"reports/{task_id}.zip"
    write_reports(root, task_id, report_dir, rep)
    return rep


def _read_state_value(root: Path, key: str) -> str | None:
    try:
        text = (root / "plan" / "STATE.md").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(rf"^{key}:[ \t]*(\S*)", text, flags=re.M)
    return match.group(1) if match else None


def print_summary(rep: dict) -> None:
    r = rep["regression"]
    regress = "skipped" if r is None else _ratio(r)
    print(f"\n{rep['verdict']}  {rep['task']}  tests={_ratio(rep['task_tests'])}  "
          f"regress={regress}  report=reports/{rep['task']}/report.md")
    for reason in rep["reasons"][:15]:
        print(f"  - {reason}")
    for note in rep["notes"]:
        print(f"  note: {note.splitlines()[0]}")
    if rep["verdict"] == "FAIL":
        print(f"\nNext: new chat, attach fitfinder.bundle + reports/{rep['task']}.zip and type\n"
              f"  Task {rep['task']} — report attached (FAIL)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one task gate and write its report.")
    parser.add_argument("task", help="task id, e.g. S00.1")
    parser.add_argument("--no-regress", action="store_true",
                        help="skip the regression suite (implies --keep-state)")
    parser.add_argument("--keep-state", action="store_true",
                        help="do not touch STATE.md / INDEX.md / PROGRESS.md")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="project root (default: the repository containing this script)")
    args = parser.parse_args(argv)
    try:
        rep = run(args.task, args.root.resolve(), args.no_regress, args.keep_state)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        return 2
    print_summary(rep)
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
