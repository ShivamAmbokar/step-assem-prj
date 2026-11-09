# HANDBOOK v4 — Auto-Mating in a STEP Assembly (OCCT-based, human-run tests)

> **Reference handbook. Do not execute it top to bottom.** Work is driven by one task card at a time (`plan/TASKS/<ID>.md`).
> A card names the sections of this handbook to read. Read only those.
>
> **Who does what**
> - **Claude (claude.ai chat):** writes code, tests and scripts for ONE task card per chat, inside its own sandbox, on an uploaded copy of the repo. It **cannot** install or run cadquery/OCP, so it cannot run OCCT-dependent tests. It delivers a patch.
> - **Human (laptop, no agents):** applies the patch, runs `python tools/run_task.py <ID>` in the project venv (cadquery/OCP, numpy, scipy, trimesh, pyvista, pytest installed from `requirements.txt`), and uploads the generated report to the next chat when it FAILS. On PASS the human commits the report and merges.
> - **Libraries, not reinvention:** STEP I/O, assembly structure, colours, B-rep queries, surface types, same-domain unification, booleans, distances and meshing come from **OCCT via cadquery/OCP**; maths from **numpy/scipy**; meshes, GLB and renders from **trimesh/pyvista**; tests from **pytest (+ pytest-json-report)**. Write new code only for the matching logic itself.
> - **Never** import `OCC.Core` (pythonocc-core): one OCCT binding per process.

## 0. Operating rules (v4)

### 0.1 Execution rules
1. **One task per chat, strictly in `plan/TASKS/INDEX.md` order.** Never work ahead.
2. **Tests first.** Each card lists test names. Write those tests (pytest) first, then the implementation. Test names map to gates: `test_gNN_k_*` ⇔ GNN.k in §8.
3. **Markers.** OCCT-dependent tests are marked `@pytest.mark.occ`; tests needing the real assembly `@pytest.mark.real`; slow ones `@pytest.mark.slow`. `tests/conftest.py` skips `occ` tests when `OCP` is not importable (Claude's sandbox), and skips `real` tests when `FITFINDER_DATA` is unset or the files are missing.
4. **Claude must never claim a test passed unless it ran.** Its report lists: ran-and-passed (pure tests), compiled-only, and *to be verified by the human run*.
5. **Never cheat a gate.** Do not change `config.py` (except in S19.2, by protocol), loosen test tolerances, skip/xfail/delete tests, special-case fixture names in library code, or read `fixtures/spec/*` / `ground_truth.json` from library code.
6. **Frozen oracles.** `fixtures/spec/*.json` (S01.1–S01.2) and `data/ground_truth/**` (S04.6–S04.7, tag `gt-v1`) are changed only by a separate `spec(fix)` / `gt(fix)` commit with evidence from a human-run report.
7. **Determinism.** Seeded RNG only (`numpy.random.default_rng(seed)`); sorted iteration; deterministic parallel merges.
8. **Real data stays on the laptop.** `data/real/` is git-ignored; `FITFINDER_DATA` points to it. Only checksums (`data/SHA256SUMS`), inventories, crops' metadata, ground truth and reports are committed.
9. **Size limits.** Modules ≤ 800 lines, functions ≤ 80 lines; `ruff check` clean.

### 0.2 The run-and-report protocol (every agent task)
1. Claude delivers `<ID>.patch` (+ `<ID>_changes.zip`) with STATE `status: AWAITING_REPORT`.
2. Human applies it on branch `task/<id>` and runs: `python tools/run_task.py <ID>`.
3. `run_task.py` (built in S00.1, extended later) does, in order:
   - reads `plan/TASKS/manifest.json` for `<ID>` (test node ids, extra commands, required artifacts, markers);
   - runs the task's tests with `pytest --json-report`, then the **regression suite** (`pytest -m "not real and not slow"`, all earlier tasks);
   - runs any `commands` of the task (script tasks: inventories, measurements, real runs) capturing stdout/stderr and produced files;
   - writes `reports/<ID>/report.json`, `reports/<ID>/report.md`, copies artifacts into `reports/<ID>/`, and zips everything to `reports/<ID>.zip`;
   - verdict **PASS** iff all task tests passed (none skipped unless the manifest allows it), the regression suite passed, all commands exited 0 and all required artifacts exist;
   - on PASS: updates `plan/STATE.md` (`current_task` → next, `status: READY`), ticks `plan/TASKS/INDEX.md`, appends a line to `PROGRESS.md`; on FAIL: sets `status: FAILING`, `last_report: reports/<ID>.zip`.
4. **PASS** → human commits `reports/<ID>/` + bookkeeping, pushes, merges (HUMAN_GIT.md). **FAIL** → human starts a new chat, attaches the repo upload + `reports/<ID>.zip`, message `Task <ID> — report attached (FAIL)`; Claude delivers a `fix(<ID>)` patch on the same branch; repeat.

### 0.3 Git
Claude commits in its sandbox and delivers patches; the human applies, runs, pushes, merges and tags (`plan/HUMAN_GIT.md`). `main` only contains tasks whose report is PASS. Never force-push `main`; never commit `fixtures/out/`, `out/`, `.cache/`, `data/real/`, `.venv/`.

### 0.4 PROGRESS.md line (written by run_task.py)
`<date> <ID> PASS|FAIL tests=<passed>/<total> regress=<passed>/<total> sha=<short> report=reports/<ID>/report.md`

---

## 1. Task brief (verbatim requirements, normalized)

**Inputs**
1. A STEP file of a **single part**: the *source part*, e.g. a chuck key.
2. The selected faces on it, given either as **face IDs** or as faces coloured **green** in that STEP.
3. A STEP file of the **assembly** the part belongs to. The source part may or may not appear in it.

**Output**
- Every face, or face group, in the assembly that the selected faces fit against or mate with.
- Which part(s) and which occurrence each match is on.
- **All** matching instances, not only the best one.
- For each match:
  - the fit class (**exact** / **clearance** / **interference**);
  - the joint type and behaviour (e.g. *exact-slip*, *sliding*);
  - the evidence used to decide.
- A highlighted render, plus a list of matched face IDs, for each test assembly.

**What makes it hard** (each point is covered by a gate; see §4)
- It must work for any selection, with no hard-coded feature shapes.
- Face types: plane, cylinder, cone and sphere are mandatory. Torus and freeform get a reported warning.
- The selected faces form a rigid group. Their mutual geometry must match, not just each face on its own.
- Exact fits (faces coincide) must be told apart from sliding/clearance fits (parallel or coaxial with a controlled gap).
- Matching must not depend on position or orientation.
- Every instance must be found.
- No false positives.

**Evaluation:**
- ≥ 3 different mating scenarios correct (keyed shaft, chuck + key, bench vice, pulley on motor shaft, …);
- all instances found;
- exact vs clearance correctly told apart;
- a clear matching criterion;
- no false positives on clearly non-matching faces;
- clean, reproducible code.

**Deliverables:**
- private GitHub repo;
- README with run instructions;
- WRITEUP.md: what was matched and why, what breaks, what you'd do with another week;
- outputs per test assembly.

---

## 2. Approach and justification (implement this; summarize it in WRITEUP.md)

**Idea: treat the selection as an automatically derived "mate reference" and solve it as a geometric-constraint problem.**

Commercial CAD does two related things:
- **SOLIDWORKS Mate References** store primary, secondary and tertiary entities plus the expected mate type.
- **SmartMates** infer coincident or concentric mates from the geometry type when a part is dragged onto another.

Both pick a *group* of reference faces and look for complementary geometry. Classical kinematics (**Reuleaux lower pairs**: prismatic, revolute, cylindrical, planar, spherical, helical) tells us what motion such a group leaves free. **Geometric constraint solving** tells us how to compute the pose that satisfies the group.

Pipeline (each stage is one or more gated steps):
1. **Describe** each face by its analytic surface type, intrinsic size and outward orientation, in the part's local frame. Convert B-splines back to analytic surfaces; merge split faces.
2. **Fingerprint the selection as a group.** Record rigid-motion-invariant relations between every pair of faces (angles, signed gaps, axis distances). Record the free DOF the group allows.
3. **Search** each target part *definition* for injective face assignments whose relations match the fingerprint, with complementary orientation (backtracking constraint satisfaction). Searching per definition makes repeated parts free.
4. **Solve the pose:**
   - rotation by Kabsch/SVD with det = +1, so mirror-image features are rejected when the matched directions span all three axes;
   - translation by least squares;
   - the null-space gives the free DOF, from which the joint type follows.
5. **Verify** per occurrence: trimmed-area overlap, collision against the whole assembly (with an allowance for interference fits), and placement along the free DOF.
6. **Classify the fit by play analysis:** an LP over linearized gaps gives the feasible displacement region.
   - empty region → **interference**;
   - zero width → **exact**;
   - positive width → **clearance**.
   This measures the actual exact/clearance distinction the task asks for, independent of how the pose solver centred the part.
7. **Mode A (in place):** if the source part is found in the assembly, also report what its selected faces touch where it already sits. This covers multi-part contact.
8. **Multi-part completion:** a pose seeded by a subset of faces on one part is completed with faces on neighbouring parts (e.g. a gib).
9. **Report** all matches, the near-misses with reason codes, and the evidence.

**Why this is the best option:**

| Alternative | Why it was rejected |
|---|---|
| Per-face matching | False positives everywhere, because any plane matches any plane. |
| Hard-coded features (holes, slots) | Not general. |
| Mesh / ICP registration | No surface semantics, no exact-vs-clearance distinction, needs a good initial pose, slow on 20 MB assemblies. |
| Learning | No training data. |

The constraint-group approach is invariant by construction, general across face types, explainable (every decision carries numbers) and naturally finds all instances.

---

## 3. Definitions

| Term | Definition |
|---|---|
| **Definition / occurrence** | A part shape stored once, and each placed instance of it (with a world 4×4 matrix and a path such as `chuck#0/pinion#2`). |
| **Local face ID** | 1-based index in `TopExp.MapShapes_s(shape, TopAbs_FACE, map)` of the **original** shape as read from STEP (same convention as FreeCAD's `FaceN`). |
| **Global face ID (gid)** | `offset[occ] + local_id`, where `offset` accumulates face counts over occurrences in XCAF traversal order (starting at 0). |
| **Match** | A pose of the source part plus, for each selected face, ≥ 1 target face (on ≥ 1 occurrence) satisfying every rule in Appendix C, with coverage of **all** selected faces. |
| **Partial match** | Coverage < 100%. Reported separately in `partial_matches`, never in `matches`, never highlighted as a match. |
| **Near-miss** | A relation-consistent face set that fails a strict check. Reported with a reason code and value; never highlighted. |
| **Play** | Largest finite width of the feasible displacement region, over the constrained directions (Appendix C11). |
| **Fit class** | `INTERFERENCE` if infeasible (depth ≤ INTERFERENCE_MAX); `EXACT` if play ≤ EXACT_GAP_TOL; `CLEARANCE` if play ≤ CLEARANCE_MAX. Otherwise the match is rejected. |
| **Joint type** | From free DOF (#T, #R): fixed, prismatic, revolute, cylindrical, planar, spherical, other. |
| **Behaviour** | EXACT+fixed → `exact-located`; EXACT+any DOF → `exact-slip`; CLEARANCE+fixed → `clearance-located`; CLEARANCE+any free T → `sliding`; CLEARANCE+R only → `running`; INTERFERENCE → `press-fit`. |

---

## 4. Traceability: evaluation criterion → where it is proven

| Criterion | Fixtures (App. A/B) | Gates |
|---|---|---|
| ≥ 3 mating scenarios | F01/F02 chuck+key; F03 keyed shaft; F04–F06 vice; F07 pulley on motor shaft; F08 taper; F09 ball; real R1–R3+ | G15, G17, G19 |
| All instances | F01 (4), F02 (5), F03 (2), F07 (2), F08 (2), F09 (3), F20 (100), real chuck | G15.*, G19.2 |
| Exact vs clearance vs interference | F04 vs F05, F02 loose socket, F07, F09 loose, F11 press fit | G11, G13, G15 |
| Group context (not per-face) | F17 clutter, F02 decoys, F03 hub_nokey, F07 motor_round | G9, G15 |
| Face types | planes F01/F10; cylinders F07/F11; cones F08; spheres F09; mixed F03/F07 | G6, G15 |
| Pose invariance | F19 + randomized fuzz | G12, G17.2 |
| No false positives | F16, F17, every decoy, real precision | G15, G19.3 |
| Multi-part mates | F18, F18A | G13, G14 |
| Robust input (splits, B-spline, inch, colours) | F12, F13, F14, green-face selection | G3, G5, G6 |
| Clean / reproducible | CI, ruff, pinned env, determinism | G0, G17, G20 |

---

## 5. Configuration — `fitfinder/config.py`

These defaults are frozen. They may change only in S19, and only per the calibration protocol.

```python
GEOM_TOL            = 1e-3   # mm  same point / same surface
ANGLE_TOL_DEG       = 0.5
EXACT_GAP_TOL       = 0.02   # mm  play <= this -> EXACT
INTERFERENCE_MAX    = 0.05   # mm  diametral / across-flats interference accepted
CLEARANCE_MAX       = 1.0    # mm  play / size clearance accepted
RELAX_MARGIN        = 2.0    # mm  relaxed search window widening
MIN_PAIR_OVERLAP    = 0.2
MIN_MEAN_OVERLAP    = 0.5
FULL_CONTACT        = 0.99
UV_GRID             = 20     # refine to 40 if < 50 interior samples
PLAY_SAMPLES_PER_PAIR = 16
BOOLEAN_FUZZY       = 1e-4
COLLISION_VOL_ABS   = 1e-3   # mm^3
COLLISION_VOL_REL   = 1e-6   # x source volume
INTERFERENCE_VOL_FACTOR = 1.5
UNDER_CONSTRAINED_T = 2      # query free translations >= this -> skip Mode B
MIN_SEED_FRACTION   = 0.5    # multi-part seeds use >= max(2, ceil(0.5 n)) faces
MAX_SEEDS           = 5000
PLATEAU_GRID        = 201
RANGE_RES           = 0.1
ROT_SAMPLES_AXIS    = 24     # 15 deg steps for a free rotation axis
MAX_RESULTS         = 500
INCLUDE_SAME_DEFINITION = False
ALL_POSES           = False
REACHABILITY        = False
DEF_TIMEOUT_S       = 30
WORKERS             = 0      # 0 = os.cpu_count()
CACHE_VERSION       = 1
BOUNDARY_EPS        = 1e-6   # inclusive class boundaries
```

A `Config` dataclass accepts overrides from tests and the CLI (`--set KEY=VALUE`).

---

## 6. Data contracts

### 6.1 CLI
```
fitfinder match   --part P.step (--faces 3,5,7 | --select-color green) --assembly A.step --out DIR
                  [--mode A|B|both] [--all-poses] [--reachability] [--set KEY=VALUE ...]
fitfinder inspect        --step X.step                 # inventory: parts, occurrences, faces by type
fitfinder inspect-faces  --step X.step --occurrence PATH   # per-face type, params, area, centroid
fitfinder measure        --step X.step --a OCC:FACE --b OCC:FACE    # angle, distance, radii, gap
fitfinder render         --step X.step [--highlight OCC:FACE,...] [--label-faces OCC] --out img.png
fitfinder extract-part   --step A.step --occurrence PATH --out part.step [--faces ids --mark-green]
fitfinder split          --step A.step --subtree PATH --out sub.step
fitfinder crop           --step A.step --around PATH --margin MM --out crop.step   # writes crop_gid_map.json
```

**Exit codes:**
- `0` — status OK or NO_FIT;
- `1` — internal ERROR, with `result.json` still written;
- `3` — invalid input: bad path, face ID out of range, nothing selected, only unsupported surfaces selected.

### 6.2 Fixture spec `fixtures/spec/Fxx.json` (hand-written in S1 from Appendix B)
```json
{ "id": "F01", "selection": {"source_part": "key", "face_points_local": [{"p":[5,0,20],"n":[1,0,0]}, ...]},
  "expected": { "status": "OK", "match_count": 4,
    "matches": [{ "mode_contains": "B", "fit_class": "EXACT", "behaviour": "exact-slip", "joint": "prismatic",
                  "targets": [{"part": "pinion", "face_points_world": [[x,y,z], ...]}],
                  "play": [0.0, 0.001], "free_translation_dir_world": [1,0,0],
                  "pose_checks": [{"source_point_local":[0,0,0], "world":[65,0,30], "tol":0.5}],
                  "ranges": {"engaged_len": [12, 0.5]} }],
    "near_misses": [{"part": "pinion_small", "reason": "SIZE_TOO_SMALL", "value": -0.4, "tol": 0.01}],
    "partial_count": 0, "warnings_contain": [] } }
```
`[a, b]` in `play` means a ≤ play ≤ b. `[v, tol]` in ranges means v ± tol.

### 6.3 Ground truth `data/ground_truth/<scenario>/ground_truth.json` (written in S4, Appendix D)
```json
{ "assembly": "data/real/wm290v/WM290V_RedrawStart.stp", "part": "part.step", "faces": [12,13,14,15],
  "expected_matches": [{"parts": ["…"], "occurrences": ["…"], "target_local_face_ids": {"occ": [..]},
                        "fit_class": "EXACT", "joint": "prismatic", "measured": {"width_a": 10.0, "width_b": 10.0}}],
  "must_not_match": [{"occurrence": "…", "why": "…"}], "evidence": ["gt_r1_match0.png"], "notes": "…" }
```

### 6.4 Result `out/result.json` (validated against `fitfinder/schema/result.schema.json`)
```json
{ "status": "OK|NO_FIT|ERROR", "warnings": [], "timing_s": {...},
  "query": {"part_file": "...", "face_ids": [...], "face_types": {...},
            "free_dof": {"T":1, "R":0, "joint":"prismatic"}, "source_occurrences": ["key#0"],
            "registration": [[4x4]] },
  "matches": [{
     "id": 0, "mode": "A|B|A+B", "fit_class": "EXACT|CLEARANCE|INTERFERENCE", "behaviour": "...",
     "joint": "prismatic", "play_mm": 0.0, "interference_mm": 0.0,
     "parts": ["pinion"], "occurrences": ["chuck#0/pinion#2"],
     "pairs": [{"query_face": 3, "targets": [{"occurrence": "...", "local_face_id": 7, "gid": 1234}],
                "overlap": 1.0, "gap_mm": 0.0}],
     "transform_world": [[4x4]],
     "free_dof": {"translations": [[...]], "rotations": [{"axis_dir": [...], "axis_point": [...]}]},
     "full_contact_range": [lo, hi] | null, "engaged_range": [lo, hi] | null,
     "score": 0.97,
     "evidence": {"relations_checked": 6, "max_angle_err_deg": 0.0, "max_dist_err_mm": 0.0,
                  "size_clearances_mm": [...], "rotation_rank": 2, "row_residual_max_mm": 0.0,
                  "overlap_mean": 1.0, "collision_volume_mm3": 0.0, "allowed_volume_mm3": 0.0,
                  "tau_star_mm": 0.0, "play_mm": 0.0} }],
  "partial_matches": [...same shape + "coverage": [k, n]],
  "near_misses": [{"occurrences": [...], "parts": [...], "target_faces": [...], "reason": "...", "value": -0.4, "detail": "..."}] }
```

**Reason codes:** `SIZE_TOO_SMALL`, `CLEARANCE_EXCEEDED`, `MIRROR_ONLY`, `POSE_RESIDUAL`, `LOW_OVERLAP`, `COLLISION`, `UNREACHABLE`.

**Warnings:**
- `UNDER_CONSTRAINED_QUERY_MODE_B_SKIPPED`
- `SOURCE_NOT_IN_ASSEMBLY`
- `UNSUPPORTED_SURFACE:<face_id>`
- `SEARCH_TIMEOUT:<definition>`
- `COLLISION_CHECK_UNCERTAIN`
- `SYMMETRIC_SOURCE_AMBIGUOUS`

### 6.5 `matched_faces.csv`
Columns: `match_id, mode, fit_class, behaviour, joint, part, occurrence, local_face_id, gid, query_face_id, overlap, gap_mm`. One row per target face.

---

## 7. Repository layout (v4)
```
fitfinder/   __init__.py __main__.py cli.py config.py schema/ occ.py (thin OCP helpers)
             loader.py faces.py selection.py tools.py render.py
             normalize.py descriptors.py fingerprint.py candidates.py search.py pose.py
             verify.py play.py collide.py identify.py mode_a.py multipart.py results.py highlight.py cache.py
fixtures/    spec/*.json  spec.schema.json  build.py  xcaf_writer.py  out/ (gitignored)
data/        SHA256SUMS  inventory/  scenarios/  ground_truth/<scenario>/  real/ (gitignored, laptop only)
tests/       conftest.py  helpers.py  test_s00_env.py … test_s20_deliverables.py  metamorphic.py
tools/       run_task.py  verify_h.py  final_report.py  check.py
reports/     <ID>/report.json  <ID>/report.md  <ID>/<artifacts>   (committed on PASS)
results/     <scenario>/{result.json, matched_faces.csv, report.md, overview.png, match_*.png, viewer.html}
plan/        HANDBOOK.md STATE.md TASKS/ (cards, INDEX.md, manifest.json) PROJECT_INSTRUCTIONS.md CHAT_MESSAGES.md HUMAN_GIT.md START_HERE.md
requirements.txt  requirements.lock (pip freeze from the human's venv)  pyproject.toml  README.md  WRITEUP.md  PROGRESS.md  CALIBRATION.md
```
`tools/check.py` = `ruff check .` + `pytest -m "not real and not slow"`.

---

## 8. Steps and gates

> Gates are normative. The **Commits** lists inside steps are superseded by task cards. Wherever a step mentions CI, `gh`, Git LFS or `make`, read: *the human runs `tools/run_task.py` on the laptop* (§0.2). "Appendix B.3" expectations are extended by **B.4** for fixtures F21–F33, which are built in S01.6 and asserted in S15.3.

### S0 — Skeleton, environment, run-and-report tooling (v4)
**Tasks**
1. `requirements.txt`: `cadquery>=2.4`, `numpy`, `scipy`, `trimesh`, `pyvista`, `pytest`, `pytest-json-report`, `ruff`. The human installs in a venv and commits `requirements.lock` (`pip freeze`).
2. `pyproject.toml` (package `fitfinder`, console script, ruff config line-length 100, pytest markers `occ`, `real`, `slow`), package skeleton (§7), `config.py` (§5), `tests/conftest.py` (marker skipping per §0.1.3, session fixture building `fixtures/out` once per content hash of `fixtures/`), `.gitignore`.
3. `tools/run_task.py` per §0.2 and Appendix I; `tools/verify_h.py` per Appendix J; `tools/check.py`; `tools/final_report.py` (skeleton, completed in S20.4).
4. `plan/TASKS/manifest.json` is provided by the plan; `run_task.py` must validate it.

**Gate G0**
- G0.1 In the human venv: `import cadquery, OCP, numpy, scipy, trimesh, pyvista` succeeds; versions are recorded in the report.
- G0.2 OCCT round trip: a 10×10×10 box written with `STEPControl_Writer` and read back has volume 1000 ± 1e-6.
- G0.3 `run_task.py` on a synthetic manifest entry produces report.json/.md/zip with correct verdicts for pass, fail, skipped-not-allowed and failing-command cases (pure-Python test using a temp project).
- G0.4 `verify_h.py H0` passes on the repo; a temp repo without `plan/` fails.
- G0.5 `ruff check .` clean.

---

### S1 — Fixture spec and builder
**Goal:** 21 deterministic synthetic assemblies, each with a source-part STEP whose selected faces are green, and a frozen oracle for each.

**Tasks**
1. Hand-write `fixtures/spec/F01…F20.json` and `F18A.json` from Appendix B. Add `fixtures/spec/spec.schema.json`.
2. In `fixtures/build.py`, implement `make_xcaf_assembly(tree, path, unit="MM")` with XCAF directly. Do not use `cq.Assembly`.
   - Add each definition once: `st.AddShape(shape, False)` and name it with `TDataStd_Name`.
   - Assemblies: `st.NewShape()`, then `st.AddComponent(parent, child, TopLoc_Location(trsf))`.
   - Call `st.UpdateAssemblies()`, then write with `STEPCAFControl_Writer`.
   - For inch output: `Interface_Static.SetCVal_s("write.step.unit","IN")`, then reset to `"MM"`.
3. Implement `make_part_step(shape, selected_points, path)`:
   - write the source part alone;
   - colour each selected face green: `lbl = st.AddSubShape(part_label, face)`, then `ColorTool.SetColor(lbl, Quantity_Color(0,1,0,Quantity_TOC_RGB), XCAFDoc_ColorSurf)`.
4. Build every fixture of Appendix A. Rules:
   - every cut tool extends ≥ 1 mm past the face it opens through;
   - every assembly that "contains the part" places it as stated.
5. Write `fixtures/out/Fxx.{assembly.step, part.step, selection.json}`.
   - `selection.json` holds face IDs, computed by reading `part.step` back with `STEPControl_Reader`, then `TopExp.MapShapes_s` and a point-on-face lookup.

**Gate G1**
- G1.1 All 21 fixtures build, and each `*.step` reloads without exception.
- G1.2 Occurrence and definition counts (parts only) match Appendix A's "Count" column.
- G1.3 Definition volumes match their analytic formulas within 1e-4 relative (1e-3 for F13):
  - key = 10²·40 + 80·12·12;
  - pinion = π·10²·30 − 10²·15;
  - F11 pin = π·5.015²·30;
  - F11 plate = 10⁵ − 10π(5² + 5² + 4.95² + 5.2² + 5.8²).
- G1.4 F12 plate: 1 solid, exactly 8 cylindrical faces.
- G1.5 F13 plate: no `GeomAbs_Plane` or `GeomAbs_Cylinder` face.
- G1.6 F14 file text contains `INCH`.
- G1.7 In every assembly, any two occurrences have common volume ≤ 1e-3 mm³. Touching is allowed; penetration is not.
- G1.8 In each `part.step`, the set of green faces (read via XCAF colours) equals the face IDs in `selection.json`.
- G1.9 Building twice gives byte-identical `selection.json` files and identical face-table hashes.
- G1.10 All spec files validate against `spec.schema.json`.

**Commits** (branch `step/s01-fixtures`)
1. `spec(s01): add frozen fixture oracles F01–F20, F18A and schema`
2. `test(s01): fixture integrity gate`
3. `feat(s01): XCAF assembly writer with shared definitions and unit option`
4. `feat(s01): part writer with green selected faces`
5. `feat(s01): build fixtures F01–F20, F18A`
6. `docs(s01): progress`

---

### S2 — Loader, occurrences, face IDs
**Goal:** read an assembly or a single part into definitions, occurrences and stable local and global face IDs.

**Tasks**
1. Write `load_assembly(path)`.
   - Before reading: `Interface_Static.SetCVal_s("xstep.cascade.unit","MM")`.
   - Read with `STEPCAFControl_Reader`, name and colour modes on.
   - Recurse from free shapes, composing `world_child = world_parent @ local`.
2. Build occurrence paths with the rule `name#k` (k = index among siblings referencing the same definition), joined by `/`, with the root omitted.
3. Write `load_part(path)`: the single solid, its face map and face colours.
4. Write the face ID helpers:
   - `local_faces(def)`;
   - `gid(occ, lid)` and `from_gid(gid)` (§3);
   - `find_face_at(def, p_local, n=None)`: exactly one face within GEOM_TOL, with its normal within 1° if `n` is given.
5. Cache loaded assemblies by (absolute path, mtime, sha256).

**Gate G2**
- G2.1 Counts match G1.2.
- G2.2 F01 pinions at θ ∈ {0, 90, 180, 270}°:
  - local origin → (50cosθ, 50sinθ, 30);
  - local +Z → (cosθ, sinθ, 0);
  - tolerance 1e-6.
- G2.3 F20: the pinion of chuck (i, j) has its origin at (400i + 50cosθ, 400j + 50sinθ, 30) ± 1e-6. All 126 paths are unique.
- G2.4 F14 matrices and bboxes equal F01's within 1e-4.
- G2.5 `from_gid(gid(occ, lid)) == (occ, lid)` for every face of F01 and F20.
- G2.6 Two loads give identical path lists and identical face tables.
- G2.7 `load_part(Fxx.part.step)` face IDs equal the IDs S1 computed.

**Commits** (branch `step/s02-loader`)
1. `test(s02): loader and face-id gate`
2. `feat(s02): XCAF assembly traversal with composed locations and paths`
3. `feat(s02): single-part loader with face colours`
4. `feat(s02): local/global face ids and point-to-face resolver`
5. `docs(s02): progress`

---

### S3 — Selection input and validation
**Goal:** turn `--faces` or `--select-color` into a validated query.

**Tasks**
1. `select_by_ids(part, ids)` and `select_by_color(part, "green" | "#RRGGBB")`.
   - "green" means g ≥ 0.6, r ≤ 0.4, b ≤ 0.4.
   - Colours are read from face sub-shape labels, falling back to the solid's colour (which is not a selection).
2. Validation:
   - IDs out of range → `InputError` (exit 3);
   - an empty selection → `InputError`;
   - surface types other than plane, cylinder, cone and sphere → warning `UNSUPPORTED_SURFACE:<id>`, and the face is dropped;
   - if all selected faces are unsupported → `InputError`.
3. Selections are normalized as sorted, de-duplicated IDs.

**Gate G3**
- G3.1 For all 21 fixtures, `select_by_color(part, "green")` == the IDs in `selection.json`.
- G3.2 Selection sizes: F01, F02, F14, F16, F19, F20 → 4; F03 → 4; F04–F06 → 5; F07 → 2; F08 → 1; F09 → 1; F10 → 6; F11–F13 → 1; F15 → 1; F17 → 4; F18, F18A → 5.
- G3.3 Face ID 0 or N+1 → `InputError`. An empty selection → `InputError`.
- G3.4 A test-built part (torus ring fused to a box), selecting the torus face plus one box face → warning, and 1 face kept. Selecting only the torus → `InputError`.
- G3.5 Permuted or duplicated ID lists give an identical query.

**Commits** (branch `step/s03-selection`)
1. `test(s03): selection gate`
2. `feat(s03): face selection by ids and by colour`
3. `feat(s03): input validation and unsupported-surface warnings`
4. `docs(s03): progress`

---

### S4 — Tooling, real-data intake, ground truth (before any matcher code)
**Goal:**
- the inspection, measurement, rendering and extraction tools;
- the real assemblies under version control;
- an independent, frozen ground truth.

**Tasks**
1. Implement the CLI subcommands `inspect`, `inspect-faces`, `measure`, `render`, `extract-part`, `split` and `crop` (§6.1).
   - `render` uses pyvista offscreen (`pv.OFF_SCREEN = True`; call `pv.start_xvfb()` if no display). It tessellates with `BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)`.
   - `crop` keeps the occurrences whose world bbox intersects the target bbox expanded by the margin. It preserves placements and writes `crop_gid_map.json` (crop gid → original gid).
2. `data/real/fetch.sh` downloads or copies the assemblies and verifies `SHA256SUMS`. Start with `WM290V_RedrawStart.stp` (≈ 21.4 MB, from the provided link) and the provided key part STEP, if one was given. Add ≥ 1 additional public assembly, e.g. a bench vice. Track them with LFS.
3. Run `fitfinder inspect` on each real assembly and commit `data/real/<asm>/inventory.md` (parts, occurrences, faces by type).
4. Define the real scenarios (Appendix D): at least R1 chuck + key (the provided key example), plus ≥ 2 more of different mating types, e.g. a dovetail slide, motor pulley on shaft, taper, keyed handwheel.
5. Per scenario, create a crop, extract or provide the source part with green faces, establish the ground truth by **measurement and renders only**, and write `ground_truth.json` plus evidence PNGs.

**Gate G4**
- G4.1 Each real assembly loads, and `inventory.md` lists the number of parts, occurrences and faces.
- G4.2 Crop and split: for 3 sampled occurrences, the world matrices equal the original's within 1e-6, local face IDs are unchanged, and `crop_gid_map` round-trips.
- G4.3 `render` produces a PNG whose pixel standard deviation is > 5, with highlight pixels present when `--highlight` is used.
- G4.4 The `measure` tool, checked against fixtures:
  - F02 pinion_loose socket wall-to-wall distance = 10.3 ± 1e-6;
  - F07 pulley bore Ø = 8.05 ± 1e-6;
  - F08 shank half-angle = 1.5° ± 1e-6;
  - F09 socket_loose radius = 10.2 ± 1e-6.
- G4.5 There are ≥ 3 real scenarios covering ≥ 3 distinct joint types, and R1 is the provided key example.
  - Every `ground_truth.json` validates against its schema.
  - Every expected match has an evidence PNG.
  - R1 lists the candidate parts found by inspection. The task states 3; if inspection disagrees, the notes explain why.
- G4.6 `git tag gt-v1` exists, and `git log` shows `gt-v1` before the first commit touching `fitfinder/normalize.py`.

**Commits** (branch `step/s04-tools-gt`)
1. `test(s04): tooling gate`
2. `feat(s04): inspect, inspect-faces and measure commands`
3. `feat(s04): offscreen renderer with face highlighting and labels`
4. `feat(s04): extract-part, split and crop with gid maps`
5. `data(s04): add real assemblies via LFS with checksums and fetch script`
6. `docs(s04): real assembly inventories`
7. `gt(s04): ground truth for real scenarios R1–Rn with evidence`, then **tag `gt-v1`**
8. `docs(s04): progress`

---

### S5 — Normalization
**Goal:** repaired shapes with merged same-domain faces and a reliable history.

**Tasks**
1. `normalize(def) -> (norm_shape, hist)`, where `hist: norm_face_id → [orig_face_ids]`.
2. Run `ShapeFix_Shape` only if `BRepCheck_Analyzer` reports the shape invalid, and chain its history.
3. Run `ShapeUpgrade_UnifySameDomain(shape, True, True, False)`, then `Build()`. Map faces through `History().Modified()`; faces that were not modified map to themselves (by `IsSame`).
4. Do not rebuild B-spline faces here.

**Gate G5**
- G5.1 Volume is unchanged within 1e-6 relative, for every definition of every fixture.
- G5.2 F12 plate: 5 cylindrical faces after normalization. `hist` maps P1, P2 and P3 to the 2 original IDs resolved from Appendix B, and P4 and P5 to 1 each.
- G5.3 F01 pinion: `hist` is the identity.
- G5.4 For every definition, the union of all `hist` values equals all original IDs, with no duplicates.

**Commits** (branch `step/s05-normalize`)
1. `test(s05): normalization gate`
2. `feat(s05): shape repair and same-domain face unification with history`
3. `docs(s05): progress`

---

### S6 — Face descriptors
**Goal:** a complete, cached `FaceDesc` per normalized face (Appendix C1–C4).

**Tasks**
1. Determine the surface type. If it is not analytic, use canonical recognition (`HAS_CANONICAL`) or the fallback fit (C3). Use `stype='other'` if neither works.
2. Sample: a UV grid filtered by `BRepClass_FaceClassifier`, with points and outward normals.
3. Compute the parameters:
   - plane: n, o;
   - cylinder: a, p, r, convex;
   - cone: oriented axis (apex → wide), apex, half-angle, convex;
   - sphere: center, r, convex;
   - plus area, centroid and bbox.
4. Adjacency and edge convexity (C4).
5. Cache per definition and count the computations.

**Gate G6**
- G6.1 **Outward-normal test** on every face of every fixture: from the first interior sample s, `s + 0.01n` is OUTSIDE the solid and `s − 0.01n` is INSIDE. 100% must pass.
- G6.2 F13 plate is recognized as 6 planes + 5 cylinders, with radii {5.0, 5.0, 4.95, 5.2, 5.8} ± 1e-4.
- G6.3 Convexity:
  - F11 pin convex, holes concave;
  - F09 ball convex, cups concave;
  - F08 shank cone convex, spindle cone concave;
  - F01 socket wall–wall edges concave, key drive vertical edges convex.
- G6.4 F01: key drive side area = 400 ± 1e-6; pinion socket wall area = 150 ± 1e-6.
- G6.5 F08 shank: half-angle 1.5° ± 1e-6 rad; apex at local z = 60 − 9/tan(1.5°) ± 1e-3; axis oriented +Z.
- G6.6 F09 ball: center (0,0,0) ± 1e-6, r = 10 ± 1e-6.
- G6.7 Calling `describe()` twice on the same definition computes once.

**Commits** (branch `step/s06-descriptors`)
1. `test(s06): descriptor gate`
2. `feat(s06): surface typing with canonical recognition and fallback fitting`
3. `feat(s06): interior sampling and outward normals`
4. `feat(s06): analytic parameters for plane/cylinder/cone/sphere`
5. `feat(s06): adjacency and edge convexity`
6. `docs(s06): progress`

---

### S7 — Query fingerprint
**Goal:** rigid-invariant relations and the free DOF of the selection.

**Tasks**
1. `relations(faces)` for all pairs (C6).
2. `free_dof(faces)` → T basis, R axes, joint type (C8).
3. `under_constrained = #T >= UNDER_CONSTRAINED_T`.
4. Characteristic size = bbox diagonal of the selected faces.

**Gate G7**
- G7.1 F01 key: 2 opposing pairs, each with s = −10 ± 1e-6; 4 perpendicular pairs; prismatic along local ±Z.
- G7.2 F10 peg: fixed.
- G7.3 F04 jaw: prismatic along ±X; the ceiling→strip relation is same-direction with s = +10.1 ± 1e-6.
- G7.4 F11 pin: cylindrical. F08 shank: revolute. F09 ball: spherical (0 T, 3 R). F03 kshaft: prismatic along ±Z. F07 pulley: prismatic along ±Z.
- G7.5 F15: planar, so `under_constrained=True`. Every other fixture: `False`.

**Commits** (branch `step/s07-fingerprint`)
1. `test(s07): fingerprint gate`
2. `feat(s07): pairwise rigid-invariant relations`
3. `feat(s07): free-DOF and joint-type analysis`
4. `docs(s07): progress`

---

### S8 — Candidate filtering
**Goal:** per query face, the target faces that could be complementary (C5, relaxed window).

**Tasks**
1. For each target definition (excluding the source definitions unless INCLUDE_SAME_DEFINITION), list the candidate target faces for every query face.
2. Bucket by type; bucket radius by 0.1 mm.
3. Record each candidate's size clearance c, so the strict classification later needs no recomputation.

**Gate G8**
- G8.1 Recall: every expected target face and near-miss face (Appendix B) is a candidate of at least one query face.
- G8.2 F11: the pin's relaxed candidates are exactly the 5 holes; its strict candidates are P1, P2 and P4.
- G8.3 F08: spindle and spindle_big cones are candidates; spindle_steep's is not.
- G8.4 No curved candidate pair has the same convexity.

**Commits** (branch `step/s08-candidates`)
1. `test(s08): candidate gate`
2. `feat(s08): complementary candidate rules and type/radius buckets`
3. `docs(s08): progress`

---

### S9 — Correspondence search
**Goal:** all relation-consistent injective assignments per target definition.

**Tasks**
1. Backtracking order: fewest candidates first; tie-break on the number of relations to already-assigned faces.
2. Relaxed relation checks (C6): the sign rule is strict; the magnitude window is relaxed.
3. Enforce injectivity.
4. Apply a per-definition timeout of DEF_TIMEOUT_S; on timeout, emit `SEARCH_TIMEOUT` and keep partial results.
5. Search once per definition, with counters.

**Gate G9**
- G9.1 F01 pinion: exactly 8 assignments, all onto the socket walls.
- G9.2 F10 block: 2 assignments (P_true and P_mirror).
- G9.3 F06 vice_body: 2. F18 vice_body (5-face single-part): 2.
- G9.4 F11 plate: 5.
- G9.5 F02: pinion_small, pinion_loose, pinion_huge and pinion_inward each have 8.
- G9.6 F03: hub 2, hub_wide 2, hub_bore22 2, hub_nokey 0.
- G9.7 F17: each clutter_rect has 8; clutter_slot, clutter_hole and clutter_boss have 0.
- G9.8 F07: motor 1 per definition; motor_10 1; motor_round 0.
- G9.9 F20: search stage ≤ 10 s; the pinion definition is searched exactly once.

**Commits** (branch `step/s09-search`)
1. `test(s09): correspondence search gate`
2. `feat(s09): backtracking relation-graph search with relaxed windows`
3. `feat(s09): per-definition timeout and counters`
4. `docs(s09): progress`

---

### S10 — Strict size check and pose solve
**Goal:** a proper rigid pose per assignment, or a precise rejection reason.

**Tasks**
1. Strict size check from the recorded c values (C5/C6):
   - c < −INTERFERENCE_MAX → `SIZE_TOO_SMALL`;
   - c > CLEARANCE_MAX → `CLEARANCE_EXCEEDED`;
   - value = the worst c.
2. Rotation (C7): enumerate axis signs for cylinders; cones use their oriented axis; rank-3 improper only → `MIRROR_ONLY`; angular error > tol → drop.
3. Translation rows and least squares (C7). Any row residual > CLEARANCE_MAX/2 + GEOM_TOL → `POSE_RESIDUAL`.
4. Free T and R (C8) from the pose.

**Gate G10**
- G10.1 F01: per pinion definition, 8 proper poses with max residual ≤ 1e-6 and 1 free T along ±Z.
- G10.2 F10: P_true is valid and fixed, and maps peg (0,0,0) to (25,30,15) ± 0.01. P_mirror → `MIRROR_ONLY`.
- G10.3 F11:
  - P1 and P2 valid, 2 poses each;
  - P4 valid;
  - P3 `SIZE_TOO_SMALL` −0.13 ± 0.005;
  - P5 `CLEARANCE_EXCEEDED` 1.57 ± 0.005.
- G10.4 F02:
  - pinion_small `SIZE_TOO_SMALL` −0.4 ± 0.01;
  - pinion_huge `CLEARANCE_EXCEEDED` 2.0 ± 0.01;
  - pinion_loose and pinion_inward valid.
- G10.5 F06: 2 valid poses, free T along ±X.
- G10.6 F08: spindle valid, revolute; shank (0,0,60) → spindle-local (0,0,100) ± 0.01; spindle_big valid at this stage.
- G10.7 F09: socket valid, spherical, center → center ± 0.01. socket_big `CLEARANCE_EXCEEDED` 2.0 ± 0.01.
- G10.8 F03: hub valid. hub_wide and hub_bore22 `CLEARANCE_EXCEEDED` 2.0 ± 0.01.
- G10.9 F07: motor valid. motor_10 `SIZE_TOO_SMALL` −1.95 ± 0.01.

**Commits** (branch `step/s10-pose`)
1. `test(s10): pose gate`
2. `feat(s10): strict size classification with reason codes`
3. `feat(s10): Kabsch rotation with chirality detection`
4. `feat(s10): least-squares translation, residuals and free DOF`
5. `docs(s10): progress`

---

### S11 — Verification, play analysis, fit classification
**Goal:** per occurrence and pose: a settled placement, overlap, collision, fit class, ranges.

**Tasks** (per target occurrence, per valid pose)
1. Build the world pose: `P = occ.world @ T_local`.
2. **Settle** (C9) to remove spurious penetration from the least-squares solve.
3. **Placement along free DOF** (C13):
   - translations: plateau search;
   - rotations: try up to ROT_SAMPLES_AXIS angles per free axis, or for spherical joints the 26 reference directions;
   - choose the first collision-free candidate.
4. **Overlap** (C10). Below thresholds → `LOW_OVERLAP`.
5. **Collision** (C12) against all occurrences except the source occurrences, with the interference allowance → `COLLISION`.
6. **Play analysis** (C11) gives the fit class, behaviour, `tau_star` and play. Play > CLEARANCE_MAX → `CLEARANCE_EXCEEDED`.
7. **Ranges** (C14). Reachability (C15) if enabled.
8. Stop at the first valid pose per (occurrence, face set) unless ALL_POSES.

**Gate G11**
- G11.1 F01 with ALL_POSES: per pinion occurrence, 4 poses pass and 4 fail with `COLLISION` — exactly the ones where key +Z maps radially inward.
- G11.2 F01 passing poses:
  - key (0,0,0) → (65cosθ, 65sinθ, 30) ± 0.5;
  - key +Z → (cosθ, sinθ, 0) ± 0.5°;
  - mean overlap ≥ 0.95;
  - engaged length 12 ± 0.5;
  - EXACT, play ≤ 1e-3, `exact-slip`.
- G11.3 F02: pinion_inward `COLLISION` with body; pinion_loose CLEARANCE, play 0.3 ± 0.01, `sliding`.
- G11.4 F06: CLEARANCE, play 0.2236 ± 0.01, `sliding`; full_contact length 140 ± 1; pose check per Appendix B.
- G11.5 F11:
  - P1, P2: INTERFERENCE, interference 0.03 ± 0.003, not rejected by collision, `press-fit`;
  - P4: CLEARANCE, play 0.37 ± 0.01, `sliding`.
- G11.6 F08: both spindles EXACT, revolute. spindle_big `LOW_OVERLAP`.
- G11.7 F09: both sockets EXACT, spherical, with a collision-free orientation found (stem outside the block). socket_loose CLEARANCE, play 0.4 ± 0.02, `running`.
- G11.8 F03: both hubs EXACT, prismatic; full_contact length 30 ± 0.5.
- G11.9 F07: both motors CLEARANCE, play 0.05 ± 0.005, `sliding`.
- G11.10 After settle, every non-interference match has all sampled gaps ≥ −1e-4.
- G11.11 With REACHABILITY, every valid F01 pose is reachable.

**Commits** (branch `step/s11-verify`)
1. `test(s11): verification and fit-class gate`
2. `feat(s11): settle step (L1 feasibility projection)`
3. `feat(s11): overlap sampling and collision with interference allowance`
4. `feat(s11): play LP and fit classification`
5. `feat(s11): free-DOF placement (plateau and rotation sampling) and ranges`
6. `feat(s11): optional reachability`
7. `docs(s11): progress`

---

### S12 — Source identification in the assembly
**Goal:** find the occurrence(s) of the source part, the part-frame → definition-frame registration, and the selected IDs mapped onto the definition.

**Tasks** (C16)
1. Signature filter: face count, volume, area, type histogram, sorted radii.
2. Registration:
   - try the identity first;
   - else use principal-axis candidates (4 proper sign combinations; sample degenerate axes in 5° steps);
   - verify with face samples.
3. Map the selected face IDs through the registration. With multiple valid registrations that map the selection differently → `SYMMETRIC_SOURCE_AMBIGUOUS`; use the first in deterministic order.
4. If none is found → warning `SOURCE_NOT_IN_ASSEMBLY`. Mode A is then skipped, but Mode B still runs.

**Gate G12**
- G12.1 F01: key → `key#0`, identity, max sample error ≤ 1e-6.
- G12.2 F19: registration = K⁻¹ ± 1e-6 (K from Appendix A), and the mapped IDs equal F01's key selection IDs.
- G12.3 F04 jaw → `jaw#0`. F18A jaw → `jaw#0`.
- G12.4 F11 pin part against the F01 assembly → `SOURCE_NOT_IN_ASSEMBLY`.
- G12.5 Pinion vs pinion_loose: not identified as each other.
- G12.6 F09 ball_stud (axisymmetric): identified; the sphere face maps correctly.

**Commits** (branch `step/s12-identify`)
1. `test(s12): source identification gate`
2. `feat(s12): congruence signatures and rigid registration`
3. `feat(s12): selection mapping and ambiguity warning`
4. `docs(s12): progress`

---

### S13 — Mode A (in place)
**Goal:** what the selected faces touch where the source part already sits, possibly on several parts.

**Tasks** (C17)
1. For each source occurrence: transform the query faces to world space and pre-filter by bbox expanded by CLEARANCE_MAX.
2. For each selected face, collect every complementary target face on any other occurrence (pair rules C17), keeping those with overlap ≥ MIN_PAIR_OVERLAP.
3. Coverage = selected faces with ≥ 1 target, divided by n.
   - Coverage 1 → one match (possibly multi-part).
   - Coverage < 1 → `partial_matches`.
4. Free DOF from all pairs, then play (C11), class, behaviour and ranges.

**Gate G13**
- G13.1 F04:
  - 1 match, coverage 5/5, single part `vice_body`, targets = the Appendix B points;
  - overlaps ≥ 0.99;
  - CLEARANCE, play 0.2236 ± 0.01, `sliding`, prismatic ±X;
  - full_contact range [−20, 120] ± 0.5.
- G13.2 F05: EXACT, play ≤ 1e-3, `exact-slip`.
- G13.3 F01, F06, F10, F11: 0 Mode A matches and 0 partial matches.
- G13.4 F15: 1 match, the plate top face, EXACT.
- G13.5 F18A: 1 multi-part match {vice_body: 4 faces, gib: 2 faces}, coverage 5/5, CLEARANCE, play 0.2 ± 0.01.
- G13.6 F04 with `--set CLEARANCE_MAX=0.05`: 0 matches, and 1 partial match with coverage 2/5 (the strips).

**Commits** (branch `step/s13-mode-a`)
1. `test(s13): in-place mode gate`
2. `feat(s13): in-place contact detection with multi-part grouping`
3. `feat(s13): coverage, partial matches and in-place classification`
4. `docs(s13): progress`

---

### S14 — Multi-part completion (Mode B)
**Goal:** fits where the selected faces mate with several parts at one pose.

**Tasks** (C18)
1. Seeds: subsets of the query of size n−1 down to max(2, ⌈MIN_SEED_FRACTION·n⌉), whose free DOF is no larger than the query's.
2. For each seed:
   - run S9–S10 on single definitions;
   - at each resulting pose (per occurrence), look for the remaining faces on other occurrences (pair rules C17 at that pose);
   - on full coverage, re-solve the pose with all pairs, then run S11 verification.
3. Cap at MAX_SEEDS. Only run completion on definitions that produced no full single-part match.

**Gate G14**
- G14.1 F18:
  - 1 multi-part match {vice_body: 4 faces, gib: 2 faces};
  - CLEARANCE, play 0.2 ± 0.01, prismatic ±X;
  - jaw (50,0,40.1) → (x, 0 ± 0.05, 40.1 ± 0.05) with 30 ≤ x ≤ 170.
- G14.2 Results for F01, F03, F07 and F17 are unchanged by enabling completion.
- G14.3 F18: seeds evaluated ≤ MAX_SEEDS, runtime ≤ 30 s.

**Commits** (branch `step/s14-multipart`)
1. `test(s14): multi-part completion gate`
2. `feat(s14): subset seeding and pose completion across occurrences`
3. `docs(s14): progress`

---

### S15 — Results assembly
**Goal:** the final match list: deduplicated, merged across modes, near-misses, evidence, status.

**Tasks**
1. Under-constrained query → Mode A only, plus warning.
2. Dedupe key: frozenset of (occurrence, original face ID) over all targets.
   - Merging Mode A with Mode B gives `A+B`, keeping Mode A's transform, ranges and DOF.
   - Within Mode B, keep the best score.
3. Near-misses: one per face set with no valid pose.
   - Reason from the furthest stage: size < mirror < residual < overlap < collision < reach.
   - Suppress a near-miss whose face set is a subset of a valid match's.
4. Score = 0.5·mean_overlap + 0.3·coverage + 0.2·(1 − clamp(play/CLEARANCE_MAX, 0, 1)).
   - Sort by score descending, then by occurrence path.
   - Cap at MAX_RESULTS.
5. Fill the `evidence` block (§6.4).
6. Status: OK, NO_FIT, or ERROR (on exception, still write the JSON).
7. Validate against `result.schema.json`.

**Gate G15:** each fixture's `result.json` equals Appendix B.3 in:
- status and match count;
- every match's parts and occurrences, target face sets (resolved from the points), mode, fit class, behaviour and joint;
- play, pose and range checks;
- near-miss set, reasons and values;
- partial count and warnings.

Additionally, every `result.json` validates against the schema.

**Commits** (branch `step/s15-results`)
1. `test(s15): results gate (Appendix B.3)`
2. `feat(s15): dedupe and A/B merge`
3. `feat(s15): near-miss consolidation and scoring`
4. `feat(s15): evidence block, status and schema validation`
5. `docs(s15): progress`

---

### S16 — Outputs: highlight, renders, lists
**Goal:** the deliverable outputs per run.

**Tasks**
1. `highlight.glb` (trimesh scene):
   - every occurrence is tessellated per face with world placement, and triangle winding is flipped for REVERSED faces;
   - colours: source faces blue (40,110,255); match targets orange (255,80,40); near-miss targets yellow (240,200,40), only with `--show-near-misses`; others grey (200,200,200);
   - a ghost of the source at each match transform, green (60,200,90, alpha 90).
2. `highlight_map.json`: occurrence → {local ID: role}.
3. Renders (pyvista offscreen, 1600×1200):
   - `overview.png`: whole assembly, non-matched parts at 25% opacity;
   - `match_<id>.png`: camera framed on the match targets' bbox (padding 30%), with the ghost shown.
4. `matched_faces.csv` (§6.5) and `report.md`: a table of matches (class, behaviour, parts, play) and near-misses.
5. `viewer/viewer.html`: self-contained, vendored three.js, loads a GLB, toggles roles.

**Gate G16**
- G16.1 The GLB loads. Mesh count = occurrences + matches (ghosts).
- G16.2 Per occurrence, the sidecar's target set equals the union of match targets, and its source set equals the selection mapping.
- G16.3 Each `match_<id>.png` has ≥ 0.1% of pixels within ±12 of the orange highlight colour. The overview's pixel std is > 5.
- G16.4 The CSV row count equals the total number of target faces. Every gid round-trips (G2.5).
- G16.5 F12: both halves of P1 and P2 are highlighted.
- G16.6 `viewer.html` opened in Playwright headless Chromium with F01's GLB shows no console errors.

**Commits** (branch `step/s16-outputs`)
1. `test(s16): outputs gate`
2. `feat(s16): GLB highlight export with ghosts and sidecar`
3. `feat(s16): offscreen overview and per-match renders`
4. `feat(s16): CSV and markdown report`
5. `feat(s16): standalone GLB viewer`
6. `docs(s16): progress`

---

### S17 — CLI, end-to-end suite, robustness
**Goal:** a proven-reliable CLI.

**Tasks**
1. `fitfinder match` wiring, exit codes (§6.1) and `--set` overrides.
2. `tests/test_s17_e2e.py` runs the CLI on all 21 fixtures and compares the results against the spec (G15 rules).
3. Robustness tests:
   - invariance fuzz: seeds 1–10 give random rigid transforms applied at the assembly root for F01, F03, F07, F09, F18;
   - selection permutation;
   - determinism: two runs give byte-identical `result.json` (excluding `timing_s`);
   - error inputs.

**Gate G17**
- G17.1 All 21 fixtures pass through the CLI.
- G17.2 Fuzz: identical match sets (occurrence and local IDs), fit classes and plays (± 1e-3). Transforms equal M·T ± 1e-4.
- G17.3 Determinism holds, and permuted selections give identical output.
- G17.4 Exit codes:
  - missing file → 3;
  - ID out of range → 3;
  - only a torus selected → 3;
  - truncated STEP → 1, with `status: ERROR` in the JSON.
- G17.5 `pytest --cov=fitfinder` line coverage is ≥ 85%. Ruff is clean.

**Commits** (branch `step/s17-e2e`)
1. `test(s17): end-to-end and robustness gate`
2. `feat(s17): match command wiring and exit codes`
3. `fix(s17): <each robustness fix, one commit per fix>`
4. `docs(s17): progress`

---

### S18 — Performance
**Goal:** usable on 20 MB assemblies.

**Tasks**
1. Disk cache: `.cache/<sha256(step)>/<definition>.pkl` holding descriptors and normalization history, keyed by CACHE_VERSION.
2. Parallelism: on Linux, a `ProcessPoolExecutor` using fork over target definitions, with results merged in sorted order.
3. Bbox pre-filters everywhere. Collision checks only against occurrences whose bboxes overlap.
4. `timing_s` per stage in the result.

**Gate G18**
- G18.1 F20: cold ≤ 120 s, warm (cached) ≤ 30 s.
- G18.2 WM290V full match for R1: cold ≤ 15 min and warm ≤ 3 min on ≥ 8 cores; peak RSS ≤ 8 GB (`/usr/bin/time -v`).
- G18.3 Parallel output equals serial output byte-for-byte (excluding timings).
- G18.4 No `SEARCH_TIMEOUT` warning on any synthetic fixture.

**Commits** (branch `step/s18-perf`)
1. `test(s18): performance gate`
2. `perf(s18): on-disk descriptor cache`
3. `perf(s18): parallel per-definition search and verification`
4. `perf(s18): bbox pre-filters and stage timings`
5. `docs(s18): progress`

---

### S19 — Real-assembly validation and calibration
**Goal:** correct on real data against `gt-v1`, with a documented and frozen configuration.

**Tasks**
1. Run every real scenario (`make real`) and compute per scenario:
   - recall = matched GT targets / GT targets;
   - precision = matches equal to a GT expected match / reported matches;
   - fit-class accuracy.
2. Write `calibration.csv` with play, tau*, overlap and residual for every match and near-miss.
3. **Calibration protocol** (the only place config may change):
   - a change must separate GT positives from GT negatives with margin;
   - record the evidence in CALIBRATION.md (table plus histogram PNG);
   - the full synthetic suite must stay green; if a change breaks a synthetic gate, it is not allowed.
4. Tag `config-frozen`.

**Gate G19**
- G19.1 Every real scenario has status OK, or NO_FIT where GT expects none.
- G19.2 Recall is 100% for every scenario. R1 highlights exactly the GT candidate parts (3 per the task statement, unless the GT notes justify otherwise).
- G19.3 Precision is 100%: no reported match outside the GT, and every `must_not_match` entry is absent from `matches`.
- G19.4 The fit class equals the GT for every match.
- G19.5 Synthetic `make check` is still green after calibration. CALIBRATION.md lists every changed key with before/after values and evidence.

**Commits** (branch `step/s19-real`)
1. `test(s19): real-assembly gate (marked real)`
2. `fix(s19): <each real-data robustness fix, one commit each, with a regression test>`
3. `chore(s19): calibration — <key>: <old> → <new>` (one commit per key), then **tag `config-frozen`**
4. `docs(s19): calibration report and progress`

---

### S20 — Deliverables
**Goal:** a repo ready for submission.

**Tasks**
1. `make results` regenerates `results/<assembly>/<scenario>/` for every real scenario and for F01, F03, F04, F07, F08, F09, F11, F17 and F18.
2. README.md and WRITEUP.md per Appendix E.
3. Add a CI job `fresh-clone`: clone, `make setup`, `make fixtures`, `make demo` on F01. It must finish green.
4. `gh release create v1.0.0` with the GLBs and the viewer attached.

**Gate G20**
- G20.1 README contains the sections in Appendix E.1. Every command in README's "Quickstart" is executed by `tests/test_s20_deliverables.py` and exits 0.
- G20.2 WRITEUP.md contains every section in Appendix E.2, plus the matching-criteria table and the results table, with numbers taken from `results/`.
- G20.3 Every results folder contains the files listed in §7.
- G20.4 The `fresh-clone` CI job is green. Release `v1.0.0` exists. The repo is still PRIVATE.

**Commits** (branch `step/s20-deliverables`)
1. `test(s20): deliverables gate`
2. `docs(s20): README with quickstart and usage`
3. `docs(s20): write-up (approach, criteria, results, limits, next week)`
4. `chore(s20): generate results for real and synthetic scenarios`
5. `ci(s20): fresh-clone smoke job`
6. `docs(s20): progress`, then merge, `tag v1.0.0`, `gh release create v1.0.0 …`

---

## Appendix A — Synthetic fixtures (mm)

**Notation:**
- `Box(x0,x1, y0,y1, z0,z1)` is an axis-aligned box.
- `Cyl(r, base_point, dir, len)` is a cylinder.
- Placements are composed right to left: `Translate ∘ Rz ∘ Ry` means Ry is applied first.
- Every fixture has `Fxx.assembly.step` and `Fxx.part.step`. The part file holds the source definition in its own local frame, with selected faces green.
- "Contains source" says whether the source part is also an occurrence in the assembly.

### A.1 Shared parts

| Name | Local geometry |
|---|---|
| `body` | `Cyl(80,(0,0,0),+Z,60)` minus, for each listed θ, a radial blind hole `Cyl(10,(50cosθ,50sinθ,30),(cosθ,sinθ,0),40)` (r ∈ [50, 90], flat bottom at r = 50). |
| `pinion` | `Cyl(10,(0,0,0),+Z,30)` minus socket `Box(−5,5,−5,5,15,31)` (10.0 × 10.0, depth 15, open at z = 30). Placement at θ: `Translate(50cosθ,50sinθ,30) ∘ Rz(θ) ∘ Ry(+90°)`. |
| `pinion_small` / `pinion_loose` / `pinion_huge` | As pinion, with socket 9.6 / 10.3 / 12.0 square. |
| `pinion_inward` | As pinion, with the 10.0 socket `Box(−5,5,−5,5,−1,15)` at the inner end, opening toward the chuck centre. |
| `key` | `Box(−5,5,−5,5,0,40)` (drive, 10.0 square, tip at z = 0) fused with handle `Box(−40,40,−6,6,40,52)`. |

### A.2 Fixtures

| ID | Name | Geometry and placements | Contains source | Count occ/def |
|---|---|---|---|---|
| F01 | chuck_exact | `body` (θ = 0,90,180,270) at identity; 4× `pinion` at those θ; `key` at `Translate(0,0,150) ∘ Rz(17°)`. | yes | 6/3 |
| F02 | chuck_decoys | F01, plus body holes at 45/135/225/315, `pinion_small`@45, `pinion_loose`@135, `pinion_inward`@225, `pinion_huge`@315. | yes | 10/7 |
| F03 | keyed_shaft_hubs | `kshaft` = `Cyl(10,(0,0,0),+Z,100)` ∪ key `Box(−3,3,8,13.5,20,80)`, placed at `Translate(0,−200,0) ∘ Ry(90°)`. `hub` = `Cyl(25,(0,0,0),+Z,30)` − bore `Cyl(10,(0,0,−1),+Z,32)` − keyway `Box(−3,3,0,13.5,−1,31)`. Placements: hub#0 `Translate(200,0,0) ∘ Rx(90°)`; hub#1 `Translate(−200,50,0) ∘ Rz(70°) ∘ Ry(30°)`. `hub_nokey` (no keyway) at `Translate(0,200,0)`. `hub_wide` (keyway x ∈ [−4,4]) at `Translate(200,200,0)`. `hub_bore22` (bore r = 11, keyway 6 wide, top y = 13.5) at `Translate(−200,−200,0)`. | yes | 6/5 |
| F04 | vice_clearance_inplace | `vice_body` = `Box(0,200,−40,40,0,30)` ∪ rail (YZ polygon `(−15,30),(15,30),(20,40),(−20,40)` extruded x ∈ [0,200]). `jaw` (local) = `Box(20,80,−40,40,30,70)` − (YZ polygon `(−14.611803,29),(14.611803,29),(20.161803,40.1),(−20.161803,40.1)` extruded x ∈ [19,81]). This is the slot offset 0.1 on the flanks and ceiling. Jaw at identity. | yes | 2/2 |
| F05 | vice_exact_inplace | As F04, but the jaw cut polygon is `(−14.5,29),(14.5,29),(20,40),(−20,40)` (zero clearance). | yes | 2/2 |
| F06 | vice_clearance_moved | F04 with the jaw at `Translate(300,300,0) ∘ Rz(90°)`. | yes | 2/2 |
| F07 | pulley_dshaft | `motor` = `Box(−21,21,−21,21,−40,0)` ∪ shaft (circle r = 4 ∩ y ≤ 3.5, extruded z ∈ [−1,24]). `motor_round`: shaft is a full circle r = 4. `motor_10`: shaft circle r = 5 ∩ y ≤ 4.5. `pulley` = `Cyl(20,(0,0,0),+Z,20)` − D-bore (circle r = 4.025 ∩ y ≤ 3.55, z ∈ [−1,21]). Placements: motor#0 identity; motor#1 `Translate(150,0,0) ∘ Rx(90°)`; motor_round `Translate(0,150,0)`; motor_10 `Translate(150,150,0)`; pulley `Translate(−150,0,50) ∘ Ry(60°)`. | yes | 5/4 |
| F08 | morse_taper | α = 1.5°, t = tan α = 0.02618592. `mt_shank` = cone frustum z ∈ [0,60], r(z) = 9 − (60 − z)t. `spindle` = `Cyl(30,(0,0,0),+Z,100)` − taper bore frustum from (z = 30, r = 9 − 70t) to (z = 101, r = 9 + t). `spindle_big`: same with mouth r = 12. `spindle_steep`: α = 3°, mouth r = 9. Placements: spindle#0 identity; spindle#1 `Translate(200,0,0) ∘ Ry(90°)`; spindle_big `Translate(0,200,0)`; spindle_steep `Translate(200,200,0)`; mt_shank `Translate(−200,0,0) ∘ Rx(40°)`. | yes | 5/4 |
| F09 | ball_socket | `ball_stud` = sphere r = 10 at origin ∪ `Cyl(4,(0,0,−35),+Z,27)`. `socket` = `Box(−20,20,−20,20,−20,0)` − sphere r = 10 at origin (cup open at z = 0). `socket_loose`: r = 10.2. `socket_big`: r = 11.0. Placements: socket#0 identity; socket#1 `Translate(100,0,0) ∘ Rx(180°)`; socket_loose `Translate(0,100,0)`; socket_big `Translate(100,100,0)`; ball_stud `Translate(−100,0,50)`. | yes | 5/4 |
| F10 | chiral_peg | `block` = `Box(0,100,0,60,0,30)` − P_true (polygon `(−6,−4),(6,−4),(6,1),(3,4),(−6,4)` + (25,30), z ∈ [15,31]) − P_mirror (same polygon with y → −y, + (75,30)). `peg` = that polygon extruded z ∈ [0,20], placed at `Translate(50,−100,80) ∘ Rz(40°) ∘ Rx(30°)`. | yes | 2/2 |
| F11 | press_fit_pins | `plate` = `Box(0,100,0,100,0,10)` − through-holes (z ∈ [−1,11]): P1 Ø10.00 @(20,20), P2 Ø10.00 @(50,20), P3 Ø9.90 @(80,20), P4 Ø10.40 @(20,70), P5 Ø11.60 @(50,70). `pin` = `Cyl(5.015,(0,0,0),+Z,30)` at `Translate(50,50,100) ∘ Rx(45°)`. | yes | 2/2 |
| F12 | split_faces | F11, with the plate split by plane y = 20 (`BRepAlgoAPI_Splitter`) and re-fused **without** SimplifyResult (1 solid; P1–P3 walls in two halves each). | yes | 2/2 |
| F13 | bspline | F11, with the plate passed through `BRepBuilderAPI_NurbsConvert`. | yes | 2/2 |
| F14 | inch_units | F01 written with `write.step.unit = "IN"` (both files). | yes | 6/3 |
| F15 | planar_flood | `plate` `Box(0,200,0,200,0,10)`; `cube` `Box(95,105,95,105,10,20)`; `box_small` (local `Box(0,5,0,5,0,5)`) × 24 at `Translate(20+40i, 20+40j, 10)`, i,j ∈ 0..4, except (2,2). | yes | 26/3 |
| F16 | no_fit | `body` (4 holes, no pinions) and `key` as in F01. | yes | 2/2 |
| F17 | clutter_negatives | `key` as F01, plus 10 clutter parts, k = 0..9, at `Translate(100·(k mod 5), 300 + 100·⌊k/5⌋, 0) ∘ Rz(15°·k)`, in this order: slot, slot, slot, rect, rect, hole, hole, hole, boss, boss. `clutter_slot` = `Box(−20,20,−20,20,0,20)` − `Box(−21,21,−5,5,5,21)`. `clutter_rect` = same box − `Box(−5,5,−6,6,5,21)`. `clutter_hole` = same box − `Cyl(5,(0,0,5),+Z,16)`. `clutter_boss` = `Box(−20,20,−20,20,0,10)` ∪ `Box(−5,5,−5,5,10,25)`. | yes | 11/5 |
| F18 | multipart_gib | `vice_body` = `Box(0,200,−40,40,0,30)` ∪ `Box(0,200,−15,15,30,40)`. `gib` = `Box(0,200,15,17,30,40)`. `jaw` (local) = `Box(20,80,−40,40,30,70)` − `Box(19,81,−15.1,17.1,29,40.1)`. Jaw at `Translate(300,300,0) ∘ Rz(90°)`. | yes | 3/3 |
| F18A | multipart_gib_inplace | F18 with the jaw at identity. | yes | 3/3 |
| F19 | invariance | F01 assembly with a root transform M = `Translate(123.4,−56.7,89.0) ∘ Rot(axis (1,2,3)/‖·‖, 37°)`. The part file contains the key geometry transformed by K = `Translate(10,20,30) ∘ Rx(25°)`. | yes | 6/3 |
| F20 | nested_grid | Subassembly `chuck` = `body` + 4× `pinion` (as F01). The top level holds 25× `chuck` at `Translate(400i,400j,0)`, i,j ∈ 0..4, plus `key` at `Translate(−300,−300,150) ∘ Rz(17°)`. | yes | 126/3 |

---

### A.3 Additional edge-case fixtures (v4)

| ID | Name | Geometry and placements (radial-chuck geometry of F01 unless stated) | Count occ/def |
|---|---|---|---|
| F21 | inch_part | F01 assembly in mm; the **part file** written with `write.step.unit = "IN"` | 6/3 |
| F22a | schema_ap203 | F01 written with `write.step.schema = "AP203"` (both files) | 6/3 |
| F22b | schema_ap242 | F01 written with schema AP242 (`AP242DIS`) | 6/3 |
| F22c | reexport | F01 assembly read by OCCT and written again (STEP → XCAF → STEP), entity order changed | 6/3 |
| F23 | thin_cover | F01 + `cover` = `Box(80,80.5,−10,10,20,40)` touching the body at the θ = 0 socket mouth | 7/4 |
| F24 | far_origin | F01 under root `Translate(1e5,−2e5,3e5)` | 6/3 |
| F25 | thresholds | `body` with holes at θ = 0,60,…,300 holding pinions with square sockets 10.020@0, 10.021@60, 9.950@120, 9.949@180, 11.000@240, 11.001@300; `key` as F01 | 8/8 |
| F26 | two_sources | F01 + second key occurrence `key#1` inserted at θ = 0: `Translate(65,0,30) ∘ Ry(90°)` | 7/3 |
| F27 | same_definition | `brick` = `Box(−10,10,−10,10,0,10)` + boss `Cyl(4,(0,0,10),+Z,3)` − pocket `Cyl(4,(0,0,−1),+Z,4)` (depth 3); brick#0 identity, brick#1 `Translate(50,0,0)`, brick#2 `Translate(0,50,0) ∘ Rz(30°)`; part file = brick | 3/1 |
| F28 | multibody_key | F01 where `key` is one product holding **two solids** (drive and handle, touching, not fused) | 6/3 |
| F29 | surface_model_target | F01 where the θ = 0 pinion is replaced by `pinion_s`: the same faces sewn into an open **shell** (no solid) | 6/4 |
| F30a | faceted_pinions | F01 where `pinion` is triangulated (`BRepMesh`, 0.05 mm) and rebuilt as a polyhedral solid (sewn triangles) | 6/3 |
| F30b | faceted_plate | F11 where `plate` is faceted the same way | 2/2 |
| F31 | deep_nesting | F01 nested 6 sub-assemblies deep; each level applies `Translate(1,2,3) ∘ Rz(7°)` and the top applies the inverse composite (world placements equal F01) | 6/3 |
| F32 | duplicate_occurrence | F01 + a second pinion occurrence with exactly the placement of pinion@0 (intentional penetration) | 7/3 |
| F33 | filleted_spindle | F08 where spindle#1 is `spindle_f`: spindle with a 1 mm fillet on the mouth edge (toroidal face) | 5/5 |

---

## Appendix B — Selections and expected results

### B.1 Selection points (source-local; `p → n`)

| Fixtures | Source | Points |
|---|---|---|
| F01, F02, F14, F16, F17, F20 | key | (5,0,20)→(1,0,0); (−5,0,20)→(−1,0,0); (0,5,20)→(0,1,0); (0,−5,20)→(0,−1,0) |
| F19 | key (transformed by K) | the F01 points and normals mapped by K |
| F03 | kshaft | (0,−10,50)→(0,−1,0); (3,11.5,50)→(1,0,0); (−3,11.5,50)→(−1,0,0); (0,13.5,50)→(0,1,0) |
| F04, F06 | jaw | (50,−30,30)→(0,0,−1); (50,30,30)→(0,0,−1); (50,0,40.1)→(0,0,−1); (50,17.611803,35)→(0,−0.894427,0.447214); (50,−17.611803,35)→(0,0.894427,0.447214) |
| F05 | jaw | (50,±30,30)→(0,0,−1); (50,0,40)→(0,0,−1); (50,17.5,35)→(0,−0.894427,0.447214); (50,−17.5,35)→(0,0.894427,0.447214) |
| F07 | pulley | (0,−4.025,10)→(0,1,0); (0,3.55,10)→(0,−1,0) |
| F08 | mt_shank | (8.214423,0,30)→(0.999657,0,−0.026177) |
| F09 | ball_stud | (0,0,10)→(0,0,1) |
| F10 | peg | (−6,0,10)→(−1,0,0); (0,−4,10)→(0,−1,0); (6,−1.5,10)→(1,0,0); (−1.5,4,10)→(0,1,0); (4.5,2.5,10)→(0.707107,0.707107,0); (−1,−1,0)→(0,0,−1) |
| F11–F13 | pin | (5.015,0,15)→(1,0,0) |
| F15 | cube | (98,98,10)→(0,0,−1) |
| F18, F18A | jaw | (50,−30,30)→(0,0,−1); (50,30,30)→(0,0,−1); (50,0,40.1)→(0,0,−1); (50,−15.1,35)→(0,1,0); (50,17.1,35)→(0,−1,0) |

### B.2 Target face points (world unless stated)

- **Pinion-type socket at θ:**
  - c = (72.5cosθ, 72.5sinθ, 30), t̂ = (−sinθ, cosθ, 0);
  - points: c ± (0,0,5) and c ± 5t̂.
  - pinion_loose: ± 5.15; pinion_small: ± 4.8; pinion_huge: ± 6.
  - F20 adds (400i, 400j, 0).
- **F03 hub** (hub-local, map with its placement): bore (0,−10,15); walls (3,11.5,15) and (−3,11.5,15); keyway top (0,13.5,15).
  - hub_wide walls: (±4, 11.5, 15).
  - hub_bore22: bore (0,−11,15).
- **F04/F05/F06 vice_body:** (100,−30,30), (100,30,30), (100,0,40), (100,17.5,35), (100,−17.5,35).
- **F07 motor** (motor-local): cylinder (0,−4,12); flat (0,3.5,12). motor_10: (0,−5,12), (0,4.5,12).
- **F08 spindle** (local): (8.083493, 0, 65). spindle_big: (11.083493, 0, 65).
- **F09 socket** (local): (0,0,−10). socket_loose: (0,0,−10.2). socket_big: (0,0,−11).
- **F10:**
  - P_true: (19,30,22.5), (25,26,22.5), (31,28.5,22.5), (23.5,34,22.5), (29.5,32.5,22.5), (24,29,15);
  - P_mirror: (69,30,22.5), (75,34,22.5), (81,31.5,22.5), (73.5,26,22.5), (79.5,27.5,22.5), (74,31,15).
- **F11/F13:** P1 (20,25,5), P2 (50,25,5), P4 (20,75.2,5). Near-misses: P3 (80,24.95,5), P5 (50,75.8,5).
- **F12:** P1 (20,25,5) and (20,15,5); P2 (50,25,5) and (50,15,5); P4 (20,75.2,5). Near-misses: P3 (80,24.95,5) and (80,15.05,5); P5 (50,75.8,5).
- **F15 plate top:** (50,50,10).
- **F17 clutter_rect** (local): (5,0,12.5), (−5,0,12.5), (0,6,12.5), (0,−6,12.5).
- **F18/F18A:**
  - vice_body: (100,−30,30), (100,30,30), (100,0,40), (100,−15,35);
  - gib: (100,16,40), (100,17,35);
  - near-miss extra body face: (100,15,35).

### B.3 Expected outcomes

| ID | Status / # | Matches | Checks | Near-misses / warnings / partial |
|---|---|---|---|---|
| F01 | OK / 4 | B; pinion#0–3; EXACT; prismatic radial; exact-slip | key (0,0,0)→(65cosθ,65sinθ,30) ± 0.5; play ≤ 1e-3; engaged 12 ± 0.5 | none |
| F02 | OK / 5 | B; 4× pinion EXACT exact-slip; pinion_loose@135 CLEARANCE play 0.3 ± 0.01, sliding | key origin → 65 mm radius at each θ ± 0.5 | pinion_small SIZE_TOO_SMALL −0.4; pinion_huge CLEARANCE_EXCEEDED 2.0; pinion_inward COLLISION |
| F03 | OK / 2 | B; hub#0, hub#1; EXACT; prismatic; exact-slip | kshaft (0,0,50) on hub axis ≤ 0.05; kshaft +Y ↦ hub +Y ± 0.5°; full_contact 30 ± 0.5 | hub_wide CLEARANCE_EXCEEDED 2.0; hub_bore22 CLEARANCE_EXCEEDED 2.0; hub_nokey absent |
| F04 | OK / 1 | A+B; vice_body; CLEARANCE play 0.2236 ± 0.01; prismatic ±X; sliding | transform = current; full_contact [−20,120] ± 0.5 | none |
| F05 | OK / 1 | A+B; vice_body; EXACT; prismatic ±X; exact-slip | full_contact [−20,120] ± 0.5 | none |
| F06 | OK / 1 | B; vice_body; CLEARANCE play 0.2236 ± 0.01; sliding | jaw (50,0,40.1)→(x, 0 ± 0.05, 40.1 ± 0.05), 30 ≤ x ≤ 170; full_contact length 140 ± 1 | none |
| F07 | OK / 2 | B; motor#0, motor#1; CLEARANCE play 0.05 ± 0.005; prismatic; sliding | pulley (0,0,10) on shaft axis ≤ 0.05; pulley +Y ↦ motor +Y ± 0.5° | motor_10 SIZE_TOO_SMALL −1.95; motor_round absent |
| F08 | OK / 2 | B; spindle#0, spindle#1; EXACT; revolute; exact-slip | shank (0,0,60) → spindle-local (0,0,100) ± 0.05; axis ± 0.5° | spindle_big LOW_OVERLAP; spindle_steep absent |
| F09 | OK / 3 | B; socket#0, socket#1 EXACT spherical exact-slip; socket_loose CLEARANCE play 0.4 ± 0.02, running | ball (0,0,0) → socket centre ± 0.05 | socket_big CLEARANCE_EXCEEDED 2.0 |
| F10 | OK / 1 | B; block (P_true); EXACT; fixed; exact-located | peg (0,0,0) → (25,30,15) ± 0.01 | block (P_mirror) MIRROR_ONLY |
| F11 | OK / 3 | B; P1, P2 INTERFERENCE 0.03 ± 0.003, press-fit; P4 CLEARANCE 0.37 ± 0.01, sliding; all cylindrical | pin (0,0,15) → (hx,hy,5) ± 0.5 | P3 SIZE_TOO_SMALL −0.13; P5 CLEARANCE_EXCEEDED 1.57 |
| F12 | OK / 3 | as F11; P1 and P2 each with 2 target faces | as F11 | as F11 (P3 with 2 faces) |
| F13 | OK / 3 | as F11 | as F11 | as F11 |
| F14 | OK / 4 | as F01 | as F01 (mm) | none |
| F15 | OK / 1 | A; plate top only; EXACT; planar | transform = current | warning UNDER_CONSTRAINED_QUERY_MODE_B_SKIPPED |
| F16 | NO_FIT / 0 | — | — | none |
| F17 | NO_FIT / 0 | — | — | exactly clutter_rect#0 and #1, CLEARANCE_EXCEEDED 2.0; partial = 0 |
| F18 | OK / 1 | B; multi-part {vice_body: 4, gib: 2}; CLEARANCE play 0.2 ± 0.01; prismatic ±X; sliding | jaw (50,0,40.1) → (x, 0 ± 0.05, 40.1 ± 0.05), 30 ≤ x ≤ 170 | vice_body CLEARANCE_EXCEEDED 2.2 (face set includes (100,15,35)) |
| F18A | OK / 1 | A+B; same multi-part; transform = current | full_contact [−20,120] ± 0.5 | same as F18 |
| F19 | OK / 4 | as F01 (same occurrences and local IDs) | transforms = M · F01 transforms ± 1e-4; registration = K⁻¹ | none |
| F20 | OK / 100 | B; every pinion; EXACT; exact-slip | key origin → (400i + 65cosθ, 400j + 65sinθ, 30) ± 0.5 | none; pinion searched once |

All near-miss values use a tolerance of ± 0.01. "Absent" means neither a match nor a near-miss.

---

### B.4 Selections and expected outcomes for A.3

Selections: F21–F26, F28–F32 use the key selection of F01 (F21: the same points, expressed in the inch part's frame — values unchanged in mm after reading); F27 uses brick points `(4,0,11.5)→(1,0,0)` (boss wall) and `(0,0,13)→(0,0,1)` (boss top); F30b uses the pin of F11; F33 uses the shank of F08.
Target points: pinion sockets per B.2 (F25 half-widths = w/2); F27 brick-local pocket wall `(4,0,1.5)` and pocket floor `(0,0,3)`; F33 per F08.

| ID | Status / # | Matches | Checks | Near-misses / warnings / flags |
|---|---|---|---|---|
| F21 | OK / 4 | = F01 | = F01 | none |
| F22a/b/c | OK / 4 | = F01 (canonical result identical) | = F01 | none |
| F23 | OK / 3 | pinion@90/180/270 as F01 | as F01 | pinion@0 COLLISION (with cover) |
| F24 | OK / 4 | = F01 | transforms = T·F01 ± 1e-6 | none |
| F25 | OK / 4 | 10.020 EXACT (play 0.020 ± 2e-4) exact-slip; 10.021 CLEARANCE 0.021 ± 2e-4 sliding; 9.950 INTERFERENCE 0.050 ± 2e-4 press-fit; 11.000 CLEARANCE 1.000 ± 2e-4 sliding | key origin → 65 mm radius at each θ ± 0.5 | 9.949 SIZE_TOO_SMALL −0.051 ± 2e-4; 11.001 CLEARANCE_EXCEEDED 1.001 ± 2e-4 |
| F26 | OK / 4 | as F01; the θ = 0 match has mode `A+B` | `source_occurrences` = [key#0, key#1] | none |
| F27 (default) | NO_FIT / 0 | — | — | warning `SAME_DEFINITION_EXCLUDED:3` |
| F27 (`INCLUDE_SAME_DEFINITION=True`) | OK / 3 | brick#0–2; EXACT; revolute; exact-slip | boss axis on pocket axis ≤ 0.05 | none |
| F28 | OK / 4 | = F01 | = F01 | none |
| F29 | OK / 4 | as F01; θ = 0 match has `collision_checked=false` | as F01 | warning `NON_SOLID_TARGET:pinion_s#0` |
| F30a | OK / 4 | as F01 (socket walls recovered as planes after unification) | as F01 | warning `FACETED_GEOMETRY:pinion` |
| F30b | NO_FIT / 0 | — | — | warning `FACETED_GEOMETRY:plate` |
| F31 | OK / 4 | = F01 (paths 6 levels deep) | = F01 | none |
| F32 | OK / 5 | as F01 + the duplicate pinion | as F01 | warning `DUPLICATE_OCCURRENCE` |
| F33 | OK / 2 | spindle#0, spindle_f#0; EXACT; revolute | as F08 | spindle_big LOW_OVERLAP; spindle_steep absent |

Config addition for boundaries: `BOUNDARY_EPS = 1e-6` (inclusive thresholds: play ≤ EXACT_GAP_TOL + ε → EXACT; ≤ CLEARANCE_MAX + ε → CLEARANCE; interference ≤ INTERFERENCE_MAX + ε accepted).

---

## Appendix C — Rules and math

**C1 Outward normal at (u, v):**
- `BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-6).Normal()`;
- negate it if `face.Orientation() == TopAbs_REVERSED`.

**C2 Plane:** n = outward normal; o = first interior sample.

**C3 Curved surfaces:**
- **Cylinder:** axis a with canonical sign (first |component| > 1e-9 positive); p = closest axis point to the first sample; r.
- **Cone:** axis oriented from apex toward increasing radius; apex; half-angle α.
- **Sphere:** centre c and r.
- **Convexity:** convex iff (s − foot_on_axis_or_centre(s)) · n_s > 0.
- **Fallback fits** (when canonical recognition is unavailable or fails):
  - plane: SVD with max |residual| ≤ GEOM_TOL;
  - cylinder: initial axis = smallest right-singular vector of the sample normals, then `least_squares`;
  - sphere: algebraic fit, then `least_squares`;
  - cone: initial axis from the normals, then `least_squares`;
  - accept a fit only if max |residual| ≤ GEOM_TOL.

**C4 Edge convexity:**
1. At the edge midpoint m, get the normals n1 and n2 of the two faces, and the edge tangent t.
2. d = ±(n1 × t), with the sign chosen so that m + 1e-3·d classifies IN face 1.
3. The edge is convex iff d·n2 < 0, and concave iff > 0.

**C5 Single-face complement and size clearance c:**
- plane ↔ any plane (no c);
- cylinder ↔ cylinder and sphere ↔ sphere, with opposite convexity:
  - c = 2(r_hole − r_shaft), the diametral clearance;
- cone ↔ cone, with opposite convexity, |Δα| ≤ ANGLE_TOL (no c);
- windows:
  - relaxed: c ∈ [−INTERFERENCE_MAX − RELAX_MARGIN, CLEARANCE_MAX + RELAX_MARGIN];
  - strict: c ∈ [−INTERFERENCE_MAX, CLEARANCE_MAX].

**C6 Pair relations** (identical formulas in query and target frames):
- **Plane–plane:**
  - c = n_i·n_j;
  - not parallel: |acos c − acos c′| ≤ ANGLE_TOL;
  - parallel: s = (o_j − o_i)·n_i, and size value d = s + s′:
    - **opposing** (c ≈ −1): if |s| > GEOM_TOL, then sign(s′) = −sign(s). The size clearance is d (relaxed/strict windows as C5).
    - **same direction** (c ≈ +1): |d| ≤ CLEARANCE_MAX + GEOM_TOL (strict) or + RELAX_MARGIN (relaxed).
- **Plane–cylinder:**
  - compare angles of |n·a|;
  - if a ∥ plane: h = (p − o)·n; require sign(h′) = −sign(h) when |h| > GEOM_TOL, and window h + h′.
- **Cylinder–cylinder:** compare angles of |a_i·a_j|; compare the axis distance (parallel axes) or the line distance; |Δ| ≤ CLEARANCE_MAX + tol (strict) or + RELAX_MARGIN (relaxed).
- **Sphere–X:** centre-to-plane signed distance, centre-to-axis distance and centre–centre distance, with the same windows.
- **Cone–X:** angle between oriented axes; apex-to-plane and apex-to-axis distances, with the same windows.

**C7 Pose solve:**
- **Direction pairs:**
  - plane: u = n_q, v = −n_t;
  - cylinder: u = a_q, v = σa_t, σ ∈ {±1} (enumerate);
  - cone: u = a_q, v = a_t (oriented; no σ).
- **Rotation:**
  1. H = Σ u vᵀ = U S Vᵀ.
  2. d = sign det(V Uᵀ); R = V diag(1, 1, d) Uᵀ.
  3. rank = #{S > 1e-6·S_max}.
  4. Require max ∠(R u, v) ≤ ANGLE_TOL.
  5. If that fails while R₀ = V Uᵀ (det −1) passes **and** rank = 3 → `MIRROR_ONLY`.
  6. Rank 1: R = Rodrigues rotation u₀ → v₀.
  7. Rank 0 (spheres only): R = I.
- **Translation rows:**
  - plane: n_tᵀ t = n_t·(o_t − R o_q);
  - cylinder: e₁, e₂ ⊥ a_t, e_kᵀ t = e_k·(p_t − R p_q);
  - sphere: t = c_t − R c_q;
  - cone: t = apex_t − R apex_q.
  - Solve with `lstsq`.
  - Row residual check: ≤ CLEARANCE_MAX/2 + GEOM_TOL.
  - Free T = right-singular vectors whose singular value is ≤ 1e-9·max, plus missing dimensions.

**C8 Free rotation and joint type:**
- A rotation about line L is free iff every face is invariant under it:
  - plane normals ∥ L;
  - cylinder and cone axes = L;
  - sphere centres on L.
- Candidate L: the first curved axis. If all faces are spheres with one common centre → 3 R. If only planes, all with parallel normals → 1 R.
- Joint type from (#T, #R): (0,0) fixed; (1,0) prismatic; (0,1) revolute; (1,1) with T ∥ axis → cylindrical; (2,1) planar; (0,3) spherical; otherwise other.

**C9 Settle (L1 feasibility projection):**
- Use the gap constraints of C11 at the solved pose: g_i + n_i·δ ≥ 0, with δ ∈ span(constrained subspace B).
- Solve with `linprog`: min Σ|z| subject to the constraints (δ = Bz).
- If infeasible (interference), use δ = argmax of the min-gap LP restricted to |z|∞ ≤ 1.
- Apply δ to the pose.

**C10 Overlap of a pair:**
1. Sample the smaller-area face.
2. Map the samples into the other face's frame.
3. Project them with `GeomAPI_ProjectPointOnSurf`.
4. A sample counts if the distance ≤ CLEARANCE_MAX + GEOM_TOL and the classifier says IN at the projected (u, v).
5. Overlap = fraction counted. Mean overlap is weighted by the smaller area.
6. A match needs every pair ≥ MIN_PAIR_OVERLAP and mean ≥ MIN_MEAN_OVERLAP, otherwise `LOW_OVERLAP`.

**C11 Play analysis → fit class:**
1. Per pair, take ≤ PLAY_SAMPLES_PER_PAIR overlap samples (farthest-point subsampling).
2. For each sample: n_i = target outward normal (pointing toward the query side); g_i = signed gap along n_i (positive = separation).
3. B = basis of the constrained subspace (orthogonal complement of the free T). δ = Bz, with box |z|∞ ≤ 10.
4. **Maximin LP:** max τ s.t. g_i + n_i·Bz ≥ τ → τ*.
   - If τ* < −EXACT_GAP_TOL/2 → INTERFERENCE, with interference = −2τ*.
   - If −2τ* > INTERFERENCE_MAX → `SIZE_TOO_SMALL`.
5. Otherwise, take the feasible set S = {z : g_i + n_i·Bz ≥ min(0, τ*)}.
   - For each direction u in the constrained subspace (13 sign-free axes for dim 3; 8 for dim 2; 1 for dim 1), solve max and min of u·Bz over S.
   - Ignore directions that reach the box (open, separating directions).
   - Play = the largest finite width (0 if none).
6. **Class:** play ≤ EXACT_GAP_TOL → EXACT; ≤ CLEARANCE_MAX → CLEARANCE; else `CLEARANCE_EXCEEDED`.
7. Behaviour per §3.
8. **Worked values:**
   - key 10.0 in socket 10.3 → play 0.3;
   - dovetail with a 0.1 normal offset on flanks and ceiling → play 0.1/sin(26.565°) = 0.2236;
   - D-bore → 0.05;
   - press fit → τ* = −0.015 → interference 0.03.

**C12 Collision:**
1. moved = `source_def.Moved(TopLoc_Location(trsf))`.
2. Against each other occurrence whose bbox intersects: `BRepAlgoAPI_Common` with `SetFuzzyValue(BOOLEAN_FUZZY)`, then take the volume.
3. Allowed volume = COLLISION_VOL_ABS + COLLISION_VOL_REL·V_src + INTERFERENCE_VOL_FACTOR·Σ_pairs(area_contact · max(0, −τ*)).
4. Collision if the volume exceeds the allowance.
5. If the boolean errors: use `BRepExtrema_DistShapeShape`; distance > 0 means no collision, otherwise warn `COLLISION_CHECK_UNCERTAIN`.

**C13 Placement along free DOF:**
- **Translation d:**
  1. L = diag(src bbox) + diag(tgt bbox).
  2. f(u) = mean overlap on PLATEAU_GRID points over [−L, L].
  3. Plateau = {f ≥ max f − 0.01}.
  4. Try candidates in order: plateau midpoint, lower end, upper end, then 20 evenly spaced inside the plateau.
- **Free rotation axis:** try 0° and then ROT_SAMPLES_AXIS evenly spaced angles.
- **Spherical:** map source-local +Z to each of the 26 directions (±axes, ±face diagonals, ±corners; normalized order: +Z first) with a minimal rotation.
- Choose the first collision-free candidate that meets the overlap thresholds; otherwise `COLLISION`.

**C14 Ranges** (one free T):
- `full_contact_range`: the largest interval containing the chosen u where every pair overlap ≥ FULL_CONTACT and there is no collision;
- `engaged_range`: the same with MIN_PAIR_OVERLAP;
- boundaries bisected to RANGE_RES; collision tested at 1 mm steps.

**C15 Reachability:** for ±d, 50 steps up to ±L; reachable if one direction is collision-free beyond the contact zone.

**C16 Source identification:**
1. Signature filter, then registration candidates: the identity, then inertia-frame candidates (`BRepGProp.VolumeProperties_s` → principal axes; 4 proper sign variants; degenerate moments → 72 rotations about the degenerate axis).
2. Verify: ≥ 99% of 5 samples per face land on a same-type definition face within GEOM_TOL.
3. Mapping: each selected part face → the definition face containing its transformed samples.

**C17 Mode A pair rules** (world, given pose):
- **Planes:** ∠(n_q, −n_t) ≤ ANGLE_TOL and gap = (o_t − o_q)·n_q ∈ [−INTERFERENCE_MAX/2, CLEARANCE_MAX].
- **Cylinders, spheres, cones:** opposite convexity; coaxial (or concentric) within CLEARANCE_MAX; radial gap in the same window.
- **Overlap:** as C10, with a distance threshold equal to the gap window.
- **Gaps for C11:** measured at the given pose (no settle).

**C18 Multi-part completion:**
1. Seed subsets sorted by size, then lexicographically.
2. For each seed pose (after settle) and each unassigned query face, apply the C17 rules against all occurrences except the source.
3. Accept if every face is covered.
4. Then re-solve the pose with all pairs (C7, rows from all parts), settle, and run C10–C14.
5. Dedupe as in S15.

**C19 False-positive guards** (all mandatory):
- the sign rule for opposing faces;
- injectivity;
- relations checked for every pair;
- det = +1;
- overlap thresholds;
- collision against the whole assembly;
- full coverage required for `matches`;
- under-constrained queries (#T ≥ 2) skip Mode B;
- near-misses and partial matches are never highlighted as matches.

---

## Appendix D — Real-assembly protocol (S4 / S19)

1. **Scenarios.** Pick ≥ 3, each a different joint or fit type:
   - **R1 (mandatory): chuck key → chuck.** Use the provided key part STEP with green faces if one was supplied; otherwise extract the key with `extract-part --mark-green` on its 4 drive faces. The task states that 3 candidate parts are highlighted for this selection.
   - **R2:** a sliding pair (e.g. cross-slide or compound dovetail, or a bench-vice jaw from an additional assembly).
   - **R3:** a shaft–hub pair (motor pulley on motor shaft, handwheel on leadscrew, keyed gear).
   - **R4** (optional): a taper (tailstock quill or spindle MT) or a spherical pair.
2. **Crop.** Use `crop --around <source or target occurrence> --margin 150` for fast iteration. Final validation runs on the **full** assembly.
3. **Ground truth by measurement only** (never by running the matcher):
   - list candidate faces with `inspect-faces`;
   - confirm widths, diameters, angles and gaps with `measure`;
   - render each expected target with `render --highlight` → evidence PNG;
   - classify the expected fit from the measured gap: ≤ 0.02 → EXACT, ≤ 1.0 → CLEARANCE, negative → INTERFERENCE;
   - list at least 2 `must_not_match` occurrences per scenario: plausible look-alikes, e.g. other square sockets, other bores.
4. **Freeze.** Commit, then tag `gt-v1`. Later changes follow §0.1 rule 4.

---

## Appendix E — Deliverable outlines

**E.1 README.md** sections, in order:
1. What it does (2 lines plus `results/` overview image);
2. Quickstart: `make setup`, `make fixtures`, `fitfinder match …` on F01, opening `out/overview.png`;
3. Inputs: face IDs vs green faces, and the face-ID convention (§3);
4. Outputs (`result.json` fields, CSV, GLB, PNGs, viewer);
5. CLI reference;
6. Running tests (`make check`, `make real`, data fetch);
7. Configuration and tolerances;
8. Repository layout;
9. Reproducibility notes (pinned lock, determinism, CI).

**E.2 WRITEUP.md** sections, in order:
1. **Problem framing:** the two fit behaviours, and why group context matters.
2. **Approach and justification:** §2 condensed, with references to Mate References, SmartMates, kinematic pairs and constraint solving, and why the alternatives were rejected.
3. **Matching criteria:** a table of each property compared, why, the tolerance used, and the gate that proves it:
   - surface type and convexity;
   - intrinsic size;
   - pairwise angles, signed gaps and axis distances;
   - chirality via det;
   - overlap;
   - collision;
   - play.
4. **Exact vs clearance vs interference:** the play analysis, with worked numbers.
5. **Results:** a table per assembly and scenario (matches, parts, fit class, play, runtime) with renders.
6. **What breaks:**
   - freeform-only selections;
   - threads modelled as cylinders;
   - gears and other higher pairs;
   - defeatured or simplified vendor models;
   - mates defined by edges or axes rather than faces;
   - multi-part combinatorics on very large selections;
   - assemblies whose own placement is wrong;
   - tolerance assumptions.
7. **With another week:**
   - learn tolerances from the assembly's existing in-place mates;
   - edge and axis references;
   - helical and gear pairs;
   - an interactive picker (a FreeCAD workbench);
   - mesh-only STEP support;
   - a GPU or BVH collision backend;
   - user feedback loop on near-misses.

---

## Appendix F — Pitfalls (read when a gate fails)

| Symptom | Likely cause |
|---|---|
| G6.1 fails | The REVERSED flip is missing, or the centroid was used on a non-convex face; use an interior sample. |
| G2.2 rotation wrong | Location composition order is reversed. |
| G9 counts too high | The opposing-plane sign rule or injectivity is missing. |
| G10.1 gives 4, not 8 poses | Rank-2 direction sets were wrongly forced to reject in-plane reflections; they are valid via a 180° flip. |
| G10.2 P_mirror accepted | The det correction is missing, or the tip face was dropped from the selection. |
| G11.1 reversed key passes | Collision is only checked against the target part; it must cover every occurrence except the source. |
| G11.10 negative gaps or G14 COLLISION on a clearance fit | The settle step is missing (the least-squares solve sinks one-sided contacts). |
| G11.5 press fit rejected | The interference allowance is missing from the collision check. |
| Play huge or zero for the vice | Open (separating) directions were not excluded, or the samples are not spread (use farthest-point sampling). |
| G5.2 history wrong | ShapeFix and UnifySameDomain histories were not chained. |
| G1.4 has 6 cylinders | The re-fuse simplified the result. |
| Boolean exceptions | Coplanar cuts (extend tools by ≥ 1 mm); BOOLEAN_FUZZY not set. |
| Green faces not found | Colours were set on the solid, not on face sub-shape labels, or the colour was read from the wrong label. |
| F20 / WM290V slow | Searching per occurrence instead of per definition; no cache; no bbox pre-filter; ALL_POSES left on. |

---

## Appendix G — Edge-case catalogue (each owned by a test)
Owner codes: **U** unit test, **F** fixture (A.2/A.3), **M** metamorphic (Appendix H), **Z** fuzz, **R** real data, **H** human gate check.

**G1 Input files**
- `.step`/`.stp`/`.STEP` extensions and `.stp.gz` (gunzip to a temp file before OCCT) (U)
- AP203 / AP214 / AP242 schemas (F22a/b)
- inch and mm, part and assembly in different units (F14, F21)
- missing file, unreadable file, truncated or corrupted STEP → exit 3/1 with JSON (Z)
- empty product (no geometry) skipped with warning (U)
- multi-solid product (F28); open shell / surface model (F29); faceted geometry (F30a/b)
- deep nesting (F31); duplicate placements (F32); left-handed placement warning (U)
- product names with unicode, spaces, commas → paths and CSV (U)

**G2 Selection**
- IDs vs green faces equal (F01–F33 part files); IDs + colour both given → IDs used + warning (U)
- ID 0, ID > N, empty, duplicates, unsorted (U)
- no green faces; colour only on the solid (U)
- near-green colours per rule g ≥ 0.6, r ≤ 0.4, b ≤ 0.4 (U)
- torus/B-spline face selected → warning, dropped; all unsupported → exit 3 (U)
- single-face selections (F09, F15); under-constrained planar selection (F15)
- source absent from assembly (U); multiple source occurrences (F26); same-definition targets (F27); source part in a different frame (F19) or unit (F21)

**G3 Geometry normalisation**
- split faces (F12); B-spline analytics (F13); faceted planes (F30a); toroidal neighbours (F33)
- reversed faces (outward-normal test over every fixture, G6.1)
- seam vs two-loop cylinders (U: build both with OCCT)

**G4 Matching**
- D4 symmetry → 8 assignments (F01); rank-2 vs rank-3 chirality (F01, F10)
- all instances (F01, F20); nested (F20, F31); far origin (F24)
- decoys: small, loose, inward, huge (F02); mirror (F10); rectangular, U-slot, round hole, boss (F17); keyway width and bore (F03); D-flat (F07); cone angle and size (F08); sphere size (F09)
- threshold boundaries ±0.001 mm (F25)
- thin-wall collision (F23); press-fit allowance (F11, F25)
- non-overlapping coplanar/cosurface faces → LOW_OVERLAP (F08 spindle_big)
- multi-part (F18, F18A); in-place partial (U); timeouts (U with tiny DEF_TIMEOUT_S)

**G5 Outputs and operations**
- empty result still writes all files (F16)
- CSV quoting (U); deterministic bytes (U); renders non-blank with highlight pixels (U)
- read-only output dir → exit 1 (U); SIGINT → partial JSON with `INTERRUPTED` (U)
- cache invalidation and corruption recovery (U)

---

## Appendix H — Test catalogue
- **Unit tests** per module (pure tests run in Claude's sandbox; `occ` tests on the laptop).
- **Fixture tests**: every spec in `fixtures/spec/` asserted at library level (S15) and CLI level (S17).
- **Metamorphic relations** (S17.2, seeds 1–10):

| ID | Relation | Fixtures |
|---|---|---|
| MR1 | Rigid transform of the assembly root → same matches, transforms premultiplied | F01, F03, F07, F09, F18 |
| MR2 | Rigid transform of the part file geometry → same matches | F01, F04 |
| MR3 | Large offset 1e5–1e6 mm → same matches (positions ± 1e-4) | F01, F11 |
| MR4 | Unit change (inch) of part and/or assembly → same matches | F01, F07 |
| MR5 | Schema change AP203/AP214/AP242 and OCCT re-export → same canonical result | F01, F08, F11 |
| MR6 | Selection ID permutation → identical result | all |
| MR7 | Duplicate a matching occurrence at a free place → count +1 | F01 |
| MR8 | Delete a matched occurrence → count −1, rest unchanged | F01 |
| MR9 | Mirror the assembly (det −1) → rank-3 fits become MIRROR_ONLY near-misses; rank-2 fits stay | F10, F01 |
| MR10 | Scale assembly ×2 only → no matches; scale both ×2 → same matches, play ×2 | F01, F02 |
| MR11 | Far-away clutter added → identical matches | F01, F07 |

- **Fuzz** (S17.3): 200 seeded corruptions of fixture STEP files (truncate, byte flips, deleted `;`, duplicated lines) → never an uncaught exception or hang (> 30 s); always exit code 1/3 with a JSON result.
- **Real tests** (`real` marker): recall, precision, fit-class accuracy against `gt-v1` (S19).
- **Performance tests** (`slow`): F20 and WM290V budgets on the human's laptop (S18).

---

## Appendix I — Reports and the final scorecard

**`reports/<ID>/report.json`** (written by `tools/run_task.py`):
```json
{ "task": "S10.1", "verdict": "PASS|FAIL", "timestamp": "...", "git": {"sha": "...", "branch": "task/s10-1", "dirty": false},
  "env": {"python": "3.11.9", "os": "...", "cpu": 8, "ram_gb": 32, "packages": {"cadquery": "...", "OCP": "...", "numpy": "..."}},
  "task_tests": {"passed": 4, "failed": 0, "skipped": 0, "duration_s": 12.3,
                 "items": [{"nodeid": "...", "outcome": "passed", "duration_s": 0.4, "gate": "G10.1", "message": ""}]},
  "regression": {"passed": 210, "failed": 0, "skipped": 3, "duration_s": 95.0, "failures": []},
  "commands": [{"cmd": "...", "exit": 0, "stdout_tail": "...", "files": ["reports/S04.4/inventory.md"]}],
  "artifacts": ["reports/S10.1/..."], "notes": [] }
```
`report.md` is the same in readable form, with failures first (nodeid, gate, assertion message, last 30 traceback lines).

**`tools/final_report.py`** writes `reports/FINAL/report.md|json`:
1. **Gates:** every gate G0–G20 and H0–H4: PASS/FAIL with the report that proved it.
2. **Fixtures:** per spec: status, match count expected/actual, every check pass/fail.
3. **Real scenarios:** recall, precision, fit-class accuracy, runtime, near-misses.
4. **Evaluation criteria** (task brief): ≥ 3 scenarios, all instances, exact vs clearance, criterion clarity (link to WRITEUP), no false positives, reproducibility — each with evidence links.
5. **Metamorphic, fuzz, performance** summaries; **known failures** with reasons.
6. **Overall extent of success:** percentage of checks passed per category and overall.

---

## Appendix J — Human-gate checks (`tools/verify_h.py Hn`, prints PASS/FAIL and writes `reports/Hn/report.json`)
| Gate | Automated checks |
|---|---|
| H0 | git repo with remote `origin`; `plan/` complete (HANDBOOK, STATE, INDEX, manifest, all cards); `plan/TASKS/manifest.json` valid |
| H1 | venv imports cadquery/OCP/numpy/scipy/trimesh/pyvista/pytest and versions equal `requirements.lock`; `FITFINDER_DATA` set; every file in `data/SHA256SUMS` exists with matching checksum; `key_part.step` reads with OCCT and has ≥ 1 green face (count reported); WM290V reads with STEPCAFControl (time and counts reported) |
| H2 | every `data/ground_truth/*/ground_truth.json` validates; every expected match has evidence images; tag `gt-v1` exists and no commit before it touches `fitfinder/match*` or the matcher modules |
| H3 | `results/` complete for every scenario; PNGs non-blank and contain highlight pixels; `reports/FINAL/report.json` exists |
| H4 | tag `v1.0.0` exists on `main`; working tree clean; README and WRITEUP contain their required sections; FINAL report overall percentage printed |

