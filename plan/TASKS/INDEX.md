# Task index — strictly in order. Agent tasks: Claude writes, you run `tools/run_task.py`, PASS → merge.

| Done | ID | Kind | Step | Gate(s) | Title |
|---|---|---|---|---|---|
| [ ] | [H0](H0.md) | human | — | H0 | Create repo, Claude Project, upload the plan |
| [ ] | [S00.1](S00.1.md) | agent | S00 | G0.1–G0.4 | Skeleton, requirements, config, conftest, run_task/verify_h tooling |
| [ ] | [H1](H1.md) | human | — | H1 | Real data on the laptop + environment check |
| [ ] | [S00.2](S00.2.md) | agent | S00 | G0.5 → gate-s00 | check tool, final_report skeleton, manifest validation; close G0 |
| [ ] | [S01.1](S01.1.md) | agent | S01 | G1.10 (part) | Spec schema + frozen specs F01–F11 |
| [ ] | [S01.2](S01.2.md) | agent | S01 | G1.10 | Frozen specs F12–F33 (incl. F18A, F22a–c, F27 variants, F30a/b) |
| [ ] | [S01.3](S01.3.md) | agent | S01 | (G1 tooling) | XCAF assembly writer and green-face part writer |
| [ ] | [S01.4](S01.4.md) | agent | S01 | G1.1–G1.9 (F01–F11) | Build fixtures F01–F11 with cadquery |
| [ ] | [S01.5](S01.5.md) | agent | S01 | G1 (F12–F20) | Build fixtures F12–F20 and F18A |
| [ ] | [S01.6](S01.6.md) | agent | S01 | G1 → gate-s01 | Build edge-case fixtures F21–F33 |
| [ ] | [S02.1](S02.1.md) | agent | S02 | G2.1–G2.4 | Assembly loader: occurrences, paths, matrices, units |
| [ ] | [S02.2](S02.2.md) | agent | S02 | G2.5–G2.7 → gate-s02 | Face IDs, gids, part loader, colours, point-to-face |
| [ ] | [S03.1](S03.1.md) | agent | S03 | G3 → gate-s03 | Selection input and validation |
| [ ] | [S04.1](S04.1.md) | agent | S04 | G4.4 | inspect, inspect-faces, measure |
| [ ] | [S04.2](S04.2.md) | agent | S04 | G4.3 | Offscreen renderer (pyvista) |
| [ ] | [S04.3](S04.3.md) | agent | S04 | G4.2 | extract-part, split, crop |
| [ ] | [S04.4](S04.4.md) | agent | S04 | G4.1 | Real inventory (human runs, Claude reads) |
| [ ] | [S04.5](S04.5.md) | agent | S04 | (G4.5 prep) | Choose scenarios R1–R3(+R4); crops and renders |
| [ ] | [S04.6](S04.6.md) | agent | S04 | (G4.5 part) | Ground truth R1 from human-run measurements |
| [ ] | [S04.7](S04.7.md) | agent | S04 | G4.5 → gate-s04 | Ground truth R2, R3(, R4) |
| [ ] | [H2](H2.md) | human | — | H2 | Ground-truth sign-off |
| [ ] | [S05.1](S05.1.md) | agent | S05 | G5 → gate-s05 | Normalization (ShapeFix + UnifySameDomain + history) |
| [ ] | [S06.1](S06.1.md) | agent | S06 | G6 → gate-s06 | Face descriptors |
| [ ] | [S07.1](S07.1.md) | agent | S07 | G7.1–G7.3 | Pairwise relations |
| [ ] | [S07.2](S07.2.md) | agent | S07 | G7 → gate-s07 | Free DOF and joint type |
| [ ] | [S08.1](S08.1.md) | agent | S08 | G8 → gate-s08 | Candidate filtering |
| [ ] | [S09.1](S09.1.md) | agent | S09 | G9 → gate-s09 | Correspondence search |
| [ ] | [S10.1](S10.1.md) | agent | S10 | G10.2–G10.4, G10.7–G10.9 | Strict size check and rotation (Kabsch, chirality) |
| [ ] | [S10.2](S10.2.md) | agent | S10 | G10 → gate-s10 | Translation solve, residuals, pose DOF |
| [ ] | [S11.1](S11.1.md) | agent | S11 | G11.10 + overlap | Settle and overlap |
| [ ] | [S11.2](S11.2.md) | agent | S11 | G11.1, G11.3, F23, F29 | Collision with interference allowance |
| [ ] | [S11.3](S11.3.md) | agent | S11 | G11.2–G11.9 (classes), F25 | Play LP and fit classification |
| [ ] | [S11.4](S11.4.md) | agent | S11 | G11 → gate-s11 | Placement along free DOF, ranges, reachability |
| [ ] | [S12.1](S12.1.md) | agent | S12 | G12 → gate-s12 | Source identification |
| [ ] | [S13.1](S13.1.md) | agent | S13 | G13 → gate-s13 | Mode A (in place) |
| [ ] | [S14.1](S14.1.md) | agent | S14 | G14 → gate-s14 | Multi-part completion |
| [ ] | [S15.1](S15.1.md) | agent | S15 | (G15 part) | Results: dedupe, merge, near-misses, score |
| [ ] | [S15.2](S15.2.md) | agent | S15 | (G15 part) | Evidence, status, schema; spec assertions F01–F11 |
| [ ] | [S15.3](S15.3.md) | agent | S15 | G15 → gate-s15 | Spec assertions F12–F33 |
| [ ] | [S16.1](S16.1.md) | agent | S16 | G16.1, G16.2, G16.5 | GLB highlight export and sidecar (trimesh) |
| [ ] | [S16.2](S16.2.md) | agent | S16 | G16 → gate-s16 | Renders, CSV, report.md, viewer.html |
| [ ] | [S17.1](S17.1.md) | agent | S17 | G17.1, G17.4 | match CLI, exit codes, end-to-end |
| [ ] | [S17.2](S17.2.md) | agent | S17 | G17.2 | Metamorphic relations MR1–MR11 |
| [ ] | [S17.3](S17.3.md) | agent | S17 | G17 → gate-s17 | Fuzz, determinism, operational edge cases |
| [ ] | [S18.1](S18.1.md) | agent | S18 | G18 → gate-s18 | Cache, parallelism, budgets |
| [ ] | [S19.1](S19.1.md) | agent | S19 | G19.1–G19.4 | Real-assembly validation (repeat until green) |
| [ ] | [S19.2](S19.2.md) | agent | S19 | G19.5 → gate-s19 | Calibration (only if needed) and freeze |
| [ ] | [H3](H3.md) | human | — | H3 | Results review |
| [ ] | [S20.1](S20.1.md) | agent | S20 | G20.3 | Generate results/ (human runs) |
| [ ] | [S20.2](S20.2.md) | agent | S20 | G20.1 | README |
| [ ] | [S20.3](S20.3.md) | agent | S20 | G20.2 | WRITEUP |
| [ ] | [S20.4](S20.4.md) | agent | S20 | G20 → gate-s20 | Final scorecard and release prep |
| [ ] | [H4](H4.md) | human | — | H4 | Submission |

Total: 53 tasks (48 Claude-written, 5 human-only).
