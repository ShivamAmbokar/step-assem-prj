"""S00.1 gate tests: environment (G0.1, G0.2), run_task (G0.3), verify_h (G0.4), config (G0.0)."""
from __future__ import annotations

import importlib
import json
import sys
import zipfile

import pytest
from helpers import (
    REPO_ROOT,
    TOOLS_DIR,
    load_tool,
    make_temp_project,
    module_version,
    run_task_cli,
)

# --------------------------------------------------------------------------------------
# G0.1 / G0.2  (need the human venv with cadquery / OCP)
# --------------------------------------------------------------------------------------


@pytest.mark.occ
def test_g00_1_imports_and_versions():
    assert sys.version_info >= (3, 10)
    versions = {}
    for mod in (
        "cadquery",
        "OCP",
        "numpy",
        "scipy",
        "trimesh",
        "pyvista",
        "pytest",
        "pytest_jsonreport",
    ):
        importlib.import_module(mod)
        version = module_version(mod)
        assert version, f"no version found for {mod}"
        versions[mod] = version
    from packaging.version import Version

    assert Version(versions["cadquery"]) >= Version("2.4")


@pytest.mark.occ
def test_g00_2_occ_box_roundtrip(tmp_path):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from fitfinder import occ

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    assert abs(occ.volume(box) - 1000.0) <= 1e-6

    path = tmp_path / "box.step"
    occ.write_step_shape(box, path)
    assert path.stat().st_size > 0

    back = occ.read_step_shape(path)
    assert abs(occ.volume(back) - 1000.0) <= 1e-6
    for got, want in zip(occ.bbox(back), (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)):
        assert abs(got - want) <= 1e-6


# --------------------------------------------------------------------------------------
# G0.3  run_task.py verdicts on a temporary project with a fake manifest (pure Python)
# --------------------------------------------------------------------------------------

PASSING = "def test_ok():\n    assert 1 + 1 == 2\n"
FAILING = "def test_ok():\n    assert 1 + 1 == 3\n"
SKIPPING = "import pytest\n\n\ndef test_ok():\n    pytest.skip('not available here')\n"
PREV_OK = "def test_prev():\n    assert True\n"
PREV_BAD = "def test_prev():\n    assert 'earlier' == 'broken'\n"
QUICK = ("--no-regress",)  # cases that do not look at the regression suite or bookkeeping


def _run_case(tmp_path, name, body, flags=(), prev=PREV_OK, **task):
    root = tmp_path / name
    files = {"tests/test_t1.py": body, "tests/test_prev.py": prev}
    make_temp_project(root, files=files, **task)
    proc = run_task_cli(root, "T1", *flags)
    report = json.loads((root / "reports" / "T1" / "report.json").read_text(encoding="utf-8"))
    return root, proc, report


def _state(root):
    text = (root / "plan" / "STATE.md").read_text(encoding="utf-8")
    return dict(
        (line.split(":", 1)[0].strip(), line.split(":", 1)[1].split("#")[0].strip())
        for line in text.splitlines()
        if ":" in line and not line.startswith("#")
    )


def test_g00_3_run_task_verdicts(tmp_path):
    # --- PASS: bookkeeping, report files and zip ---------------------------------------
    root, proc, rep = _run_case(tmp_path, "pass", PASSING)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rep["verdict"] == "PASS"
    assert rep["task"] == "T1"
    assert rep["task_tests"]["passed"] == 1 and rep["task_tests"]["failed"] == 0
    assert rep["task_tests"]["items"][0]["nodeid"].endswith("test_t1.py::test_ok")
    assert rep["regression"]["passed"] == 2 and rep["regression"]["failed"] == 0
    assert rep["env"]["python"] and "numpy" in rep["env"]["packages"]
    assert (root / "reports" / "T1" / "report.md").is_file()
    with zipfile.ZipFile(root / "reports" / "T1.zip") as zf:
        names = zf.namelist()
    assert "T1/report.json" in names and "T1/report.md" in names
    state = _state(root)
    assert state["current_task"] == "HX" and state["status"] == "READY"
    assert state["last_completed"] == "T1"
    assert "| [x] | [T1](T1.md)" in (root / "plan" / "TASKS" / "INDEX.md").read_text()
    progress = (root / "PROGRESS.md").read_text(encoding="utf-8")
    assert " T1 PASS tests=1/1 regress=2/2 " in progress

    # --- --keep-state leaves the bookkeeping files alone --------------------------------
    root, proc, rep = _run_case(tmp_path, "keep", PASSING, flags=("--keep-state",))
    assert proc.returncode == 0 and rep["verdict"] == "PASS"
    assert _state(root)["current_task"] == "T1"
    assert "| [ ] | [T1](T1.md)" in (root / "plan" / "TASKS" / "INDEX.md").read_text()

    # --- FAIL: failing task test, failure listed first in report.md ---------------------
    root, proc, rep = _run_case(tmp_path, "fail", FAILING)
    assert proc.returncode == 1
    assert rep["verdict"] == "FAIL"
    assert rep["task_tests"]["failed"] == 1
    md = (root / "reports" / "T1" / "report.md").read_text(encoding="utf-8")
    assert "test_t1.py::test_ok" in md
    assert md.index("test_t1.py::test_ok") < md.index("## Environment")
    state = _state(root)
    assert state["status"] == "FAILING" and state["last_report"] == "reports/T1.zip"
    assert "| [ ] | [T1](T1.md)" in (root / "plan" / "TASKS" / "INDEX.md").read_text()

    # --- skipped test: FAIL unless the manifest allows it --------------------------------
    _, proc, rep = _run_case(tmp_path, "skip_bad", SKIPPING, flags=QUICK)
    assert proc.returncode == 1 and rep["verdict"] == "FAIL"
    assert rep["task_tests"]["skipped"] == 1
    _, proc, rep = _run_case(tmp_path, "skip_ok", SKIPPING, flags=QUICK, allow_skip=True)
    assert proc.returncode == 0 and rep["verdict"] == "PASS"

    # --- failing command ---------------------------------------------------------------
    _, proc, rep = _run_case(
        tmp_path, "cmd_bad", PASSING, flags=QUICK, commands=['python -c "import sys; sys.exit(3)"']
    )
    assert proc.returncode == 1 and rep["verdict"] == "FAIL"
    assert rep["commands"][0]["exit"] == 3

    # --- command producing a required artifact: PASS and the artifact is copied -----------
    make = "import pathlib; pathlib.Path('made.txt').write_text('x')"
    root, proc, rep = _run_case(
        tmp_path, "art_ok", PASSING, flags=QUICK,
        commands=[f'python -c "{make}"'], artifacts=["made.txt"],
    )
    assert proc.returncode == 0 and rep["verdict"] == "PASS", proc.stdout
    assert rep["commands"][0]["exit"] == 0
    assert (root / "reports" / "T1" / "made.txt").read_text() == "x"

    # --- missing required artifact -------------------------------------------------------
    _, proc, rep = _run_case(
        tmp_path, "art_missing", PASSING, flags=QUICK, artifacts=["out/never.txt"]
    )
    assert proc.returncode == 1 and rep["verdict"] == "FAIL"
    assert any("never.txt" in reason for reason in rep["reasons"])

    # --- listed test does not exist ------------------------------------------------------
    _, proc, rep = _run_case(
        tmp_path, "no_test", PASSING, flags=QUICK, tests=["test_does_not_exist"]
    )
    assert proc.returncode == 1 and rep["verdict"] == "FAIL"
    assert any("test_does_not_exist" in reason for reason in rep["reasons"])

    # --- regression suite failure alone is enough to FAIL --------------------------------
    _, proc, rep = _run_case(tmp_path, "regress_bad", PASSING, prev=PREV_BAD)
    assert proc.returncode == 1 and rep["verdict"] == "FAIL"
    assert rep["task_tests"]["passed"] == 1
    assert rep["regression"]["failed"] == 1
    assert any("test_prev" in f["nodeid"] for f in rep["regression"]["failures"])

    # --- --no-regress skips the suite and never touches the bookkeeping ------------------
    root, proc, rep = _run_case(tmp_path, "noreg", PASSING, flags=("--no-regress",), prev=PREV_BAD)
    assert proc.returncode == 0 and rep["verdict"] == "PASS"
    assert rep["regression"] is None
    assert _state(root)["current_task"] == "T1"


# --------------------------------------------------------------------------------------
# G0.4  verify_h.py H0
# --------------------------------------------------------------------------------------


def test_g00_4_verify_h0(tmp_path):
    verify_h = load_tool("verify_h")

    report = verify_h.run_gate("H0", REPO_ROOT)
    failed = [c for c in report["checks"] if not c["ok"]]
    assert report["verdict"] == "PASS", failed

    empty = tmp_path / "no_plan"
    empty.mkdir()
    bad = verify_h.run_gate("H0", empty)
    assert bad["verdict"] == "FAIL"
    assert any(not c["ok"] for c in bad["checks"])

    import subprocess

    script = str(TOOLS_DIR / "verify_h.py")
    proc = subprocess.run(
        [sys.executable, script, "H0", "--root", str(empty)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1 and "FAIL" in proc.stdout
    written = json.loads((empty / "reports" / "H0" / "report.json").read_text(encoding="utf-8"))
    assert written["verdict"] == "FAIL" and written["gate"] == "H0"

    proc = subprocess.run(
        [sys.executable, script, "H0", "--root", str(REPO_ROOT), "--no-write"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0 and "PASS" in proc.stdout, proc.stdout + proc.stderr

    for gate in ("H2", "H3", "H4"):
        with pytest.raises(NotImplementedError):
            verify_h.run_gate(gate, REPO_ROOT)


# --------------------------------------------------------------------------------------
# G0.0  config (HANDBOOK section 5) with override / from_cli
# --------------------------------------------------------------------------------------

HANDBOOK_DEFAULTS = {
    "GEOM_TOL": 1e-3,
    "ANGLE_TOL_DEG": 0.5,
    "EXACT_GAP_TOL": 0.02,
    "INTERFERENCE_MAX": 0.05,
    "CLEARANCE_MAX": 1.0,
    "RELAX_MARGIN": 2.0,
    "MIN_PAIR_OVERLAP": 0.2,
    "MIN_MEAN_OVERLAP": 0.5,
    "FULL_CONTACT": 0.99,
    "UV_GRID": 20,
    "PLAY_SAMPLES_PER_PAIR": 16,
    "BOOLEAN_FUZZY": 1e-4,
    "COLLISION_VOL_ABS": 1e-3,
    "COLLISION_VOL_REL": 1e-6,
    "INTERFERENCE_VOL_FACTOR": 1.5,
    "UNDER_CONSTRAINED_T": 2,
    "MIN_SEED_FRACTION": 0.5,
    "MAX_SEEDS": 5000,
    "PLATEAU_GRID": 201,
    "RANGE_RES": 0.1,
    "ROT_SAMPLES_AXIS": 24,
    "MAX_RESULTS": 500,
    "INCLUDE_SAME_DEFINITION": False,
    "ALL_POSES": False,
    "REACHABILITY": False,
    "DEF_TIMEOUT_S": 30,
    "WORKERS": 0,
    "CACHE_VERSION": 1,
    "BOUNDARY_EPS": 1e-6,
}


def test_g00_0_config_overrides():
    import dataclasses

    from fitfinder.config import DEFAULT, Config

    cfg = Config()
    assert cfg.to_dict() == HANDBOOK_DEFAULTS
    assert list(cfg.to_dict()) == list(HANDBOOK_DEFAULTS)
    assert DEFAULT == cfg
    for key, value in HANDBOOK_DEFAULTS.items():
        assert getattr(cfg, key) == value
        assert type(getattr(cfg, key)) is type(value), key

    # override() returns a modified copy and leaves the original alone
    new = cfg.override(GEOM_TOL=5e-3, MAX_SEEDS=10, ALL_POSES=True, CLEARANCE_MAX=2)
    assert (new.GEOM_TOL, new.MAX_SEEDS, new.ALL_POSES) == (5e-3, 10, True)
    assert new.CLEARANCE_MAX == 2.0 and isinstance(new.CLEARANCE_MAX, float)
    assert cfg.GEOM_TOL == 1e-3 and cfg.MAX_SEEDS == 5000 and cfg.ALL_POSES is False
    assert cfg.override() == cfg

    # frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.GEOM_TOL = 1.0  # type: ignore[misc]

    # from_cli() parses KEY=VALUE with the type of the field
    cli = Config.from_cli(["GEOM_TOL=1e-2", "ALL_POSES=true", "MAX_SEEDS=7", "WORKERS=4"])
    assert cli.GEOM_TOL == 1e-2 and cli.ALL_POSES is True
    assert cli.MAX_SEEDS == 7 and cli.WORKERS == 4
    assert Config.from_cli([]) == cfg
    assert Config.from_cli(["ALL_POSES=0", "REACHABILITY=yes"]).REACHABILITY is True
    assert Config.from_cli(["INCLUDE_SAME_DEFINITION=False"]).INCLUDE_SAME_DEFINITION is False
    base = Config.from_cli(["GEOM_TOL=2e-3"])
    assert Config.from_cli(["MAX_SEEDS=3"], base=base).GEOM_TOL == 2e-3

    # bad input is rejected
    for bad in (["NOPE=1"], ["GEOM_TOL"], ["GEOM_TOL=abc"], ["ALL_POSES=maybe"], ["MAX_SEEDS=2.5"]):
        with pytest.raises(ValueError):
            Config.from_cli(bad)
    with pytest.raises(ValueError):
        cfg.override(NOPE=1)
    with pytest.raises(ValueError):
        cfg.override(MAX_SEEDS=2.5)
    with pytest.raises(ValueError):
        cfg.override(ALL_POSES=1)

    # WORKERS=0 means "all cores"
    assert cfg.effective_workers() >= 1
    assert cfg.override(WORKERS=3).effective_workers() == 3
