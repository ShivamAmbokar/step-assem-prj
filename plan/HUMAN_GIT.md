# HUMAN_GIT — your commands: git, venv, runs, troubleshooting

**Conventions:**
- `main` holds only tasks whose run was **PASS**.
- Each task has a branch `task/<id>`, e.g. `task/s11-3`.
- Merges use `--no-ff`.
- Tags mark milestones: `gate-sNN`, `gt-v1`, `config-frozen`, `v1.0.0`.
- Never force-push `main`. Never commit `.venv/`, `data/real/`, `fixtures/out/`, `out/` or `.cache/`.

## 1. One-time setup
```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git config --global core.autocrlf false        # Windows: keep files byte-exact
```

## 2. Create the repo and upload the plan (H0)
```bash
# github.com → New repository → fitfinder → Private → Add a README → Create
git clone https://github.com/<you>/fitfinder.git && cd fitfinder
cp -r /path/to/unzipped/plan ./plan            # Windows: xcopy /E /I C:\path\plan plan
git add plan && git commit -m "chore(plan): v4 task plan" && git push origin main
```

## 3. Python environment (first done in S00.1, after its patch is applied)
```bash
cd fitfinder
python3.11 -m venv .venv                       # Windows: py -3.11 -m venv .venv
source .venv/bin/activate                      # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip freeze > requirements.lock                 # commit this with the S00.1 report
python -c "import cadquery, OCP; print('ok', cadquery.__version__)"
```
If `pip install cadquery` fails on your OS or Python version, try Python 3.11 or 3.12 (cadquery publishes wheels for those). Report the error in a chat if it persists.

**Every new terminal:** `cd fitfinder && source .venv/bin/activate` (and `FITFINDER_DATA` must be set: §8).

## 4. Apply a patch, run, report, merge (every agent task)
```bash
cd fitfinder && source .venv/bin/activate
git switch main && git pull --ff-only origin main
git switch task/<id> 2>/dev/null || git switch -c task/<id>
git am --3way --keep-cr ~/Downloads/<ID>.patch
python tools/run_task.py <ID>                  # prints PASS or FAIL; writes reports/<ID>/ and reports/<ID>.zip
```

**ZIP fallback** (if `git am` fails):
```bash
git am --abort
unzip -o ~/Downloads/<ID>_changes.zip -d .     # Windows: Expand-Archive -Force <zip> .
git rm <files listed under DELETED>            # if any
git add -A && git commit -m "feat(<ID>): <summary from Claude's report>"
```

**On FAIL:**
```bash
git bundle create ~/Downloads/fitfinder.bundle --all
# new chat: attach fitfinder.bundle + reports/<ID>.zip ; "Task <ID> — report attached (FAIL)"
git am --3way --keep-cr ~/Downloads/<ID>.patch # the fix patch, same branch
python tools/run_task.py <ID>
```

**On PASS** (`run_task.py` already updated `STATE.md`, `INDEX.md` and `PROGRESS.md`):
```bash
git add reports/<ID> plan/STATE.md plan/TASKS/INDEX.md PROGRESS.md
git commit -m "chore(report): <ID> PASS"
git push -u origin task/<id>                   # optional backup of the branch
git switch main && git pull --ff-only origin main
git merge --no-ff task/<id> -m "merge(<ID>): <title>" && git push origin main
git push origin --delete task/<id> 2>/dev/null; git branch -d task/<id>
git bundle create ~/Downloads/fitfinder.bundle --all
```

## 5. Tags (when a card lists one, after the merge)
```bash
git tag -a gate-s11 -m "S11.4 PASS" && git push origin gate-s11
git tag -a gt-v1 -m "ground truth v1" && git push origin gt-v1           # after S04.7, before S05.1
git tag -a config-frozen -m "config frozen" && git push origin config-frozen   # after S19.2
```

## 6. Release (H4)
```bash
git tag -a v1.0.0 -m "fitfinder v1.0.0" && git push origin v1.0.0
```
On GitHub: *Releases › Draft a new release* › tag `v1.0.0` › paste `reports/FINAL/report.md` as the notes › attach the GLB and `viewer.html` files from `results/` › *Publish*.

## 7. Useful run options
| Command | Purpose |
|---|---|
| `python tools/run_task.py <ID> --no-regress` | Quick re-run of only the task's tests while you iterate. The final PASS must include regression, so rerun without the flag before merging. |
| `python tools/check.py` | Lint plus every non-real, non-slow test |
| `python tools/verify_h.py H1` | Human-gate checks |
| `python tools/final_report.py` | Scorecard so far (any time) |
| `pytest tests/test_s11_verify.py -k thresholds -x -q` | Debug a single test |

## 8. Real data (H1): stays on the laptop
```bash
mkdir -p data/real                              # git-ignored
cp /path/WM290V_RedrawStart.stp /path/key_part.step data/real/
export FITFINDER_DATA="$PWD/data/real"          # add to ~/.zshrc or ~/.bashrc
#   Windows PowerShell: $env:FITFINDER_DATA="$PWD\data\real"   (and setx FITFINDER_DATA "<path>" to persist)
cd data/real && sha256sum WM290V_RedrawStart.stp key_part.step > ../SHA256SUMS && cd ../..
#   macOS: shasum -a 256 …    Windows: Get-FileHash -Algorithm SHA256 <file>
python tools/verify_h.py H1
```

## 9. Troubleshooting
| Problem | Fix |
|---|---|
| `git am`: patch does not apply | `git am --abort`. Make sure you're on the right branch: a fresh branch from the latest `main` for a first round, or the existing `task/<id>` for a fix round. Retry, or use the ZIP fallback, or chat message 4. |
| `previous rebase directory still exists` | `git am --abort` (or delete `.git/rebase-apply`) |
| `ModuleNotFoundError: OCP` / `cadquery` | Activate the venv; `pip install -r requirements.txt` |
| `run_task.py` says tests were skipped and fails | `occ` skipped means the venv isn't active. `real` skipped means `FITFINDER_DATA` isn't set or the files are missing (§8). |
| PASS locally, but you want a second opinion | Rerun in a fresh terminal: `python tools/run_task.py <ID>`. Results must be identical (determinism is a gate). |
| `! [rejected] main` | `git fetch origin && git reset --hard origin/main`, then redo the merge (only on `main`, right after a merge) |
| Merge conflict in `STATE.md` or `INDEX.md` | Keep the most advanced `current_task` and all ticks, then `git add` and `git commit` |
| Merge conflict in code | `git merge --abort`. New chat: "rebase task <ID> onto the attached bundle". |
| Accidentally committed `.venv` or `data/real` | `git rm -r --cached .venv data/real` and commit. If it was already pushed, tell Claude in a chat and consider rotating the repo history with GitHub support. |
| A run takes very long | Use `--no-regress` while iterating. Slow and real tests only run in tasks that list them. |
| Undo an applied patch before merging | `git switch main && git branch -D task/<id>`, then start again |
| Undo a merge already pushed | `git revert -m 1 <merge-sha> && git push origin main` |
