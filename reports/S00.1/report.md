# S00.1 — PASS

- time: 2026-11-09T17:22:18Z  git: e71e68b1b79669f3cc56829971c077848705f404 (task/s00-1) dirty=True
- task tests: 5 passed, 0 failed, 0 skipped
- regression: 5 passed, 0 failed, 0 skipped

## Failures

None.

## Task tests

| test | gate | outcome | s |
|---|---|---|---|
| tests/test_s00_env.py::test_g00_1_imports_and_versions | G0.1 | passed | 2.046 |
| tests/test_s00_env.py::test_g00_2_occ_box_roundtrip | G0.2 | passed | 0.009 |
| tests/test_s00_env.py::test_g00_3_run_task_verdicts | G0.3 | passed | 10.877 |
| tests/test_s00_env.py::test_g00_4_verify_h0 | G0.4 | passed | 3.445 |
| tests/test_s00_env.py::test_g00_0_config_overrides | G0.0 | passed | 0.004 |

## Commands

None.

## Artifacts

None.

## Environment

```json
{
 "python": "3.12.3",
 "os": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39",
 "cpu": 16,
 "ram_gb": 9.5,
 "packages": {
  "cadquery": "2.8.0",
  "OCP": "7.9.3.1.1",
  "numpy": "2.5.4",
  "scipy": "1.18.1",
  "trimesh": "5.2.0",
  "pyvista": "0.49.2",
  "pytest": "9.2.0",
  "pytest-json-report": "1.5.0"
 }
}
```

## Notes

None.
