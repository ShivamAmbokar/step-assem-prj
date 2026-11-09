#!/usr/bin/env python3
"""Human-gate checks (HANDBOOK Appendix J).

    python tools/verify_h.py H0|H1|H2|H3|H4 [--root DIR] [--no-write]

Prints PASS/FAIL with one line per check and writes ``reports/<Hn>/report.json`` (unless
``--no-write``). Exit code: 0 PASS, 1 FAIL, 2 usage error, 3 gate not implemented yet.
H0 and H1 are implemented here; H2-H4 follow with the tasks that produce their inputs.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_task  # noqa: E402

H1_MODULES = ("cadquery", "OCP", "numpy", "scipy", "trimesh", "pyvista", "pytest")
KEY_PART = "key_part.step"
WM290V = "WM290V_RedrawStart.stp"
PLAN_FILES = ("HANDBOOK.md", "STATE.md", "TASKS/INDEX.md", "TASKS/manifest.json")


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


# ------------------------------------------------------------------------------ H0


def check_h0(root: Path) -> tuple[list[dict], dict]:
    """Git repo with remote origin; plan/ complete; manifest valid."""
    checks = []
    top = run_task._git(root, "rev-parse", "--show-toplevel")
    is_repo = top is not None and Path(top).resolve() == root.resolve()
    checks.append(_check("git_repo", is_repo, top or f"{root} is not the top of a git work tree"))
    remotes = (run_task._git(root, "remote") or "").split()
    checks.append(_check("remote_origin", "origin" in remotes, f"remotes: {remotes}"))
    plan = root / "plan"
    missing = [rel for rel in PLAN_FILES if not (plan / rel).is_file()]
    checks.append(_check("plan_files", not missing, f"missing: {missing}" if missing else "ok"))
    try:
        manifest = run_task.load_manifest(root)
        checks.append(_check("manifest_valid", True, f"{len(manifest['order'])} tasks"))
        absent = [t for t in manifest["order"] if not (plan / "TASKS" / f"{t}.md").is_file()]
        detail = f"missing cards: {absent}" if absent else "ok"
        checks.append(_check("task_cards", not absent, detail))
    except ValueError as exc:
        checks.append(_check("manifest_valid", False, str(exc)))
        checks.append(_check("task_cards", False, "manifest unusable"))
    return checks, {}


# ------------------------------------------------------------------------------ H1


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(path: Path) -> dict[str, str]:
    """``pip freeze`` output -> {normalised name: version} (``name==version`` lines only)."""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?==([^\s;#]+)", line.strip())
        if match:
            pins[_norm(match.group(1))] = match.group(2)
    return pins


def _check_module(module: str, pins: dict[str, str] | None) -> dict:
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - report any import problem
        return _check(f"import_{module}", False, f"{type(exc).__name__}: {exc}")
    dists = importlib.metadata.packages_distributions().get(module, []) or [module]
    installed = {}
    for dist in dists:
        try:
            installed[dist] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    if pins is None:
        return _check(f"import_{module}", False, f"imports; requirements.lock missing {installed}")
    for dist, version in installed.items():
        if _norm(dist) in pins:
            same = pins[_norm(dist)] == version
            return _check(f"import_{module}", same, f"{dist} installed {version}, "
                          f"lock {pins[_norm(dist)]}")
    return _check(f"import_{module}", False, f"not pinned in requirements.lock ({installed})")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_sha256sums(root: Path, data_dir: Path | None) -> dict:
    """Every file listed in data/SHA256SUMS exists (below FITFINDER_DATA) with its checksum."""
    sums = root / "data" / "SHA256SUMS"
    if not sums.is_file():
        return _check("sha256sums", False, "data/SHA256SUMS not found")
    if data_dir is None:
        return _check("sha256sums", False, "FITFINDER_DATA is not set")
    problems, count = [], 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if not match:
            continue
        count += 1
        wanted, rel = match.group(1).lower(), match.group(2)
        target = next((p for p in (data_dir / rel, root / "data" / rel, root / rel) if p.is_file()),
                      None)
        if target is None:
            problems.append(f"missing: {rel}")
        elif _sha256(target) != wanted:
            problems.append(f"checksum mismatch: {rel}")
    if count == 0:
        problems.append("no entries in data/SHA256SUMS")
    return _check("sha256sums", not problems, "; ".join(problems) or f"{count} files verified")


def _find_data_file(data_dir: Path, name: str) -> Path | None:
    direct = data_dir / name
    if direct.is_file():
        return direct
    return next(iter(sorted(data_dir.rglob(name))), None)


def _open_xcaf(path: Path):
    """Read a STEP file into an XCAF document; return (doc, shape_tool, color_tool, free_labels)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    app.InitDocument(doc)
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEPCAFControl could not read {path}")
    if not reader.Transfer(doc):
        raise RuntimeError(f"STEPCAFControl could not transfer {path}")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    return doc, shape_tool, color_tool, free


def _map_shapes(shape_tool, free, kind):
    """Unique sub-shapes of one kind (e.g. TopAbs_FACE) over all free shapes."""
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape

    found = TopTools_IndexedMapOfShape()
    for i in range(1, free.Length() + 1):
        TopExp.MapShapes_s(shape_tool.GetShape_s(free.Value(i)), kind, found)
    return found


def count_green_faces(shape_tool, color_tool, free) -> dict:
    """Faces coloured green (HANDBOOK S3: g >= 0.6, r <= 0.4, b <= 0.4), via XCAF colours."""
    from OCP.Quantity import Quantity_Color
    from OCP.TopAbs import TopAbs_ShapeEnum
    from OCP.XCAFDoc import XCAFDoc_ColorType

    faces = _map_shapes(shape_tool, free, TopAbs_ShapeEnum.TopAbs_FACE)
    coloured = green = 0
    for i in range(1, faces.Extent() + 1):
        face, color, found = faces.FindKey(i), Quantity_Color(), False
        for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
            if color_tool.GetColor(face, kind, color):
                found = True
                break
        if found:
            coloured += 1
            if color.Green() >= 0.6 and color.Red() <= 0.4 and color.Blue() <= 0.4:
                green += 1
    return {"faces": faces.Extent(), "coloured_faces": coloured, "green_faces": green}


def _count_occurrences(label, definitions: set) -> int:
    from OCP.TCollection import TCollection_AsciiString
    from OCP.TDF import TDF_Label, TDF_LabelSequence, TDF_Tool
    from OCP.XCAFDoc import XCAFDoc_ShapeTool

    entry = TCollection_AsciiString()
    TDF_Tool.Entry_s(label, entry)
    definitions.add(entry.ToCString())
    if not XCAFDoc_ShapeTool.IsAssembly_s(label):
        return 0
    components = TDF_LabelSequence()
    XCAFDoc_ShapeTool.GetComponents_s(label, components)
    total = 0
    for i in range(1, components.Length() + 1):
        referred = TDF_Label()
        if XCAFDoc_ShapeTool.GetReferredShape_s(components.Value(i), referred):
            total += 1 + _count_occurrences(referred, definitions)
    return total


def check_key_part(data_dir: Path | None) -> tuple[dict, dict]:
    if data_dir is None:
        return _check("key_part_green_faces", False, "FITFINDER_DATA is not set"), {}
    path = _find_data_file(data_dir, KEY_PART)
    if path is None:
        return _check("key_part_green_faces", False, f"{KEY_PART} not found in {data_dir}"), {}
    try:
        _doc, shape_tool, color_tool, free = _open_xcaf(path)
        counts = count_green_faces(shape_tool, color_tool, free)
    except Exception as exc:  # noqa: BLE001
        return _check("key_part_green_faces", False, f"{type(exc).__name__}: {exc}"), {}
    counts["path"] = str(path)
    detail = f"{counts['green_faces']} green of {counts['faces']} faces"
    return _check("key_part_green_faces", counts["green_faces"] >= 1, detail), counts


def check_wm290v(data_dir: Path | None) -> tuple[dict, dict]:
    if data_dir is None:
        return _check("wm290v_reads", False, "FITFINDER_DATA is not set"), {}
    path = _find_data_file(data_dir, WM290V)
    if path is None:
        return _check("wm290v_reads", False, f"{WM290V} not found in {data_dir}"), {}
    try:
        from OCP.TopAbs import TopAbs_ShapeEnum

        start = time.perf_counter()
        _doc, shape_tool, _color, free = _open_xcaf(path)
        read_s = time.perf_counter() - start
        definitions: set = set()
        occurrences = sum(_count_occurrences(free.Value(i), definitions)
                          for i in range(1, free.Length() + 1))
        info = {
            "path": str(path), "read_s": round(read_s, 2), "free_shapes": free.Length(),
            "occurrences": occurrences, "definitions": len(definitions),
            "solids": _map_shapes(shape_tool, free, TopAbs_ShapeEnum.TopAbs_SOLID).Extent(),
            "faces": _map_shapes(shape_tool, free, TopAbs_ShapeEnum.TopAbs_FACE).Extent(),
        }
    except Exception as exc:  # noqa: BLE001
        return _check("wm290v_reads", False, f"{type(exc).__name__}: {exc}"), {}
    detail = (f"read in {info['read_s']} s: {info['occurrences']} occurrences, "
              f"{info['definitions']} definitions, {info['solids']} solids, {info['faces']} faces")
    return _check("wm290v_reads", info["free_shapes"] >= 1, detail), info


def check_h1(root: Path) -> tuple[list[dict], dict]:
    """venv matches requirements.lock; data on disk with matching checksums; key part and
    WM290V read with OCCT."""
    lock = root / "requirements.lock"
    pins = parse_lock(lock) if lock.is_file() else None
    checks = [_check_module(module, pins) for module in H1_MODULES]
    env_value = os.environ.get("FITFINDER_DATA", "").strip()
    data_dir = Path(env_value) if env_value and Path(env_value).is_dir() else None
    checks.append(_check("fitfinder_data", data_dir is not None,
                         env_value or "FITFINDER_DATA is not set"))
    checks.append(check_sha256sums(root, data_dir))
    key_check, key_info = check_key_part(data_dir)
    wm_check, wm_info = check_wm290v(data_dir)
    return checks + [key_check, wm_check], {"key_part": key_info, "wm290v": wm_info}


# ------------------------------------------------------------------------------ H2 - H4


def check_h2(root: Path):
    raise NotImplementedError("H2 is not implemented yet")


def check_h3(root: Path):
    raise NotImplementedError("H3 is not implemented yet")


def check_h4(root: Path):
    raise NotImplementedError("H4 is not implemented yet")


GATES = {"H0": check_h0, "H1": check_h1, "H2": check_h2, "H3": check_h3, "H4": check_h4}


def run_gate(gate: str, root: Path) -> dict:
    """Run the checks of one gate and return its report (nothing is written)."""
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate!r}; expected one of {sorted(GATES)}")
    root = Path(root)
    checks, extra = GATES[gate](root)
    return {
        "gate": gate,
        "verdict": "PASS" if all(c["ok"] for c in checks) else "FAIL",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": run_task.git_info(root),
        "env": run_task.env_info(),
        "checks": checks,
        "extra": extra,
    }


def write_report(root: Path, report: dict) -> Path:
    out_dir = Path(root) / "reports" / report["gate"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the automated checks of a human gate.")
    parser.add_argument("gate", help="H0 .. H4")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--no-write", action="store_true", help="do not write reports/<Hn>/")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        report = run_gate(args.gate.upper(), root)
    except NotImplementedError as exc:
        print(f"{args.gate}: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for check in report["checks"]:
        print(f"  [{'ok' if check['ok'] else 'FAIL'}] {check['name']}: {check['detail']}")
    if not args.no_write:
        print(f"report: {write_report(root, report)}")
    print(f"{report['verdict']} {report['gate']}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
