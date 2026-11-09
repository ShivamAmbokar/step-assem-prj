# START HERE — fitfinder v4: Claude writes, you run

- **Claude (claude.ai chats)** writes the code and the tests, one task card per chat. It builds on the CAD libraries (cadquery/OCP), plus numpy, scipy, trimesh and pyvista. It can't run them, because its sandbox has no pip access, so it only checks syntax and the pure-Python tests.
- **You (laptop, no agents)** apply Claude's patch, then run `python tools/run_task.py <ID>`. That runs the task's tests and the full regression suite, then writes `reports/<ID>/report.md` and `reports/<ID>.zip`.
  - **PASS:** commit the report, merge, and move to the next task. `run_task.py` updates `plan/STATE.md` for you.
  - **FAIL:** upload the report zip to a new chat; Claude fixes it; you rerun.
- **At the end,** `python tools/final_report.py` produces `reports/FINAL/report.md`: the scorecard showing how far everything succeeded (gates, test models, real scenarios, evaluation criteria, overall percentage).

## Files in `plan/`

| File | For |
|---|---|
| `START_HERE.md` | You: this guide |
| `PROJECT_INSTRUCTIONS.md` | Paste once into the Claude Project's custom instructions |
| `CHAT_MESSAGES.md` | The few messages you type |
| `HUMAN_GIT.md` | Your git, venv, run and troubleshooting commands |
| `STATE.md` | Next task and status (`run_task.py` keeps it current) |
| `TASKS/INDEX.md` | 53 tasks in order (48 written by Claude, 5 human-only) |
| `TASKS/<ID>.md` | One card: what to attach, what Claude reads and does, the tests, your exact commands |
| `TASKS/manifest.json` | Machine-readable list of each task's tests, commands and artifacts, read by `run_task.py` |
| `HANDBOOK.md` | Full technical reference; Claude reads only the sections a card names |

## Setup
1. **H0:** private GitHub repo plus this `plan/` folder; create the Claude Project; Python 3.11 installed.
2. **S00.1:** the first chat. Claude writes the skeleton, `requirements.txt` and the run/verify tools. You create the venv and `pip install -r requirements.txt` (the card shows how), then run `python tools/run_task.py S00.1`.
3. **H1:** put WM290V and the key part in `data/real/` on your laptop (never committed), set `FITFINDER_DATA`, then run `python tools/verify_h.py H1`, which must print PASS.

## The loop (each agent task)
1. Start a new chat. Attach `fitfinder.bundle` and type `Task <ID>`.
2. Download `<ID>.patch`, then run the card's section 6: `git am` on `task/<id>`, then `run_task.py <ID>`.
3. **PASS:** commit the report, merge, tag if the card says so, and make a new bundle.
4. **FAIL:** new chat, attach the bundle plus `reports/<ID>.zip`, type `Task <ID> — report attached (FAIL)`. Apply the fix patch and rerun.

**Script tasks** (S04.4–S04.7, S19.1, S20.1) run commands on the real assembly. Their reports carry the inventories, measurements and renders that Claude needs for the next chat, because only your laptop has the data.

## Human gates
Each one has an automated check, `python tools/verify_h.py Hn`, which must print PASS:

| Gate | When | What |
|---|---|---|
| H0 | start | Repo, Project, plan uploaded (re-checked automatically once S00.1 lands) |
| H1 | after S00.1 | Environment matches `requirements.lock`; data checksums; key part and WM290V readable by OCCT |
| H2 | after S04.7 | Ground-truth sign-off; tag `gt-v1` exists before any matcher code |
| H3 | after S20.1 | Results complete; renders non-blank and highlighted |
| H4 | end | Release `v1.0.0`; README/WRITEUP complete; final scorecard printed |

## Rules of thumb
- One task per chat, in INDEX order. A task is done only when **your** run says PASS.
- If a patch touches files outside the card's Scope, or edits `fixtures/spec/`, `data/ground_truth/` or `config.py` without the card asking, don't merge it. Ask why.
- Expect 1–3 fix rounds on OCCT-heavy tasks: Claude can't execute OCP, so first drafts of OCCT calls may need correcting. The report's tracebacks make each round quick.
- Real data never leaves your laptop. Only the inventories, measurements, renders and ground truth derived from it go into reports and chats. Confirm that's acceptable for your assignment.
