# Verification: a loop book that tracks a coordinator

| Requirement | Evidence | Result |
|---|---|---|
| Skills, rules, and durable specs conform to the validators | `uv run python hooks/validate_all.py .` printed "All skills, rules, and durable specs passed validation cleanly." | pass |
| Package tests pass, with every new test seen red first | `uv run --with pytest pytest -q`: 419 passed. Each unit's new tests were run against an archive of the previous commit: WU3 11 failed, WU4 11 failed, WU5 9 failed, WU6 7 failed, WU7 4 failed, WU8 7 failed; the passes in those runs were negative cases (nothing recorded, nothing quoted) | pass |
| Host seam keeps behavior and works with herdr, env-only, and no host | `tests/test_pi_host.py`: adapter detection, link and result parsing, liveness, and a book replayed with no subagent tool, with an id-less `subagent` result, and as an env-only child | pass |
| A landing by push, rebase, squash, or an integrator's push is recorded from ref state | `tests/test_pi_coordinator.py` `TestLanding`: rules `ancestor`, `patch-id`, `content`; `self` and `exact` flags; a partial landing records nothing and `read` shows `partial 1/2`; a notice git cannot confirm is `verified: false` and names the fetch | pass |
| No bash command text is parsed for pushes; the anchor recognition code and its tests are untouched | `git diff 72078f9 HEAD -- pi/book.ts` has no hunk in `anchorRun`, `anchorExit`, `locate`, `beforeRun`, `COMMAND_POSITION`; the landing tests use stand-in command text such as `land-it` | pass |
| Checkpoints, links, child books, orphans, and units behave as `spec.md` states | `TestObserve`, `TestNudge`, `TestLinks`, `TestChildBook`, `TestOrphans`, `TestUnits` | pass |
| The second thought judges on evidence entries and ignores Jev's move in its key | `tests/test_pi_anchorloop.py`: a todo update does not re-judge; a flapping move sends one advisory | pass |
| Two existing tests changed with the spec | The stage tool's enum gained `landed` and its size budget went from 400 to 460 tokens (`test_pi_book.py`); a prose `Reality anchor:` line is no longer quoted as a command (`test_pi_phases.py`). No other existing test was edited | pass |
| Versions agree at 2.11.0 | `package.json`, `pyproject.toml`, `uv.lock`; `tests/test_manifests.py` passed | pass |
| A fresh-context reader and a fresh-context reviewer confirm the change | Not run here: the coordinator dispatches the final reviewer. `rerun: n/a — review is dispatched by the coordinator` | unknown |
| A live pi-herdr-agents session produces the shapes the adapter reads | The adapter follows `PiStartedMetadata`, `PiCompletedMetadata`, and `<session>.process.json` as read from pi-herdr-agents at 6f530b9; no live session was run | unknown |
