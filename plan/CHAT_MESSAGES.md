# CHAT_MESSAGES — what you type (start a new chat in the `fitfinder` Project each time)

Always attach `fitfinder.bundle`, made with `git bundle create ~/Downloads/fitfinder.bundle --all` after your last merge, or after applying a patch when you're in a fix round.

**1. Start a task** (first round)
```
Task S11.3
```

**2. Your run failed:** attach the bundle and `reports/S11.3.zip`
```
Task S11.3 — report attached (FAIL)
```
Apply the new patch on the same `task/s11-3` branch, then run `python tools/run_task.py S11.3` again.

**3. A script task needs a follow-up chat** (S04.4–S04.7, S19.1): attach the bundle and the PASS or FAIL report zip
```
Task S04.6 — measurements attached, write the ground truth
```

**4. `git am` failed:** attach the bundle
```
Task S11.3 — git am failed with:
<paste the error lines>
Rebase onto the attached bundle and deliver a fresh patch.
```

**5. Stuck after 3 fix rounds on the same failure**
```
Task S11.3 — still failing after 3 rounds (reports attached). Explain the root cause first, propose 2 options, then implement the one you recommend.
```

**6. Not sure what's next**
```
Read plan/STATE.md and plan/TASKS/INDEX.md and tell me the next task and what to attach. Don't start it.
```
