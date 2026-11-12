# Loop book model: a coordinator running many tasks

A TLA+ model of the loop book of a straw-boss coordinator: the main of a Herdr tab that runs two units at once, each a todo with its own anchor, each worked by its own pi-herdr-agents worker in its own worktree, with one persistent reviewer, sb car notices, and the many wakes such a session gets. The model beside it (`../LoopBook.tla`) covers one unit; this one covers what one unit's steps do to the other, and what the turn-end notice says while workers are out. A change to `pi/support/units.ts`, `pi/support/book.ts`, `pi/support/landing.ts`, `pi/book.ts`, or `pi/second-thought.ts` edits `MultiTask.tla` first and reruns the checks.

The rules were proposed on 2026-11-12, and the boss decided them the same day (issues #10 to #16, the comments on #6 and #7): `proposed` is the chosen design, except M6, which P5 replaces by the quiet per unit. The code since 2.16.0 builds it; the replays in `tests/test_model_multitask.py` pass. Where the code goes past the model: the notice also names every other unit that waits on its own line and counts it as asked; a run made in a tree that is not its unit's stands until a change of that unit in that tree; the handoff names the book by its id, and the new session passes it as `resume` (P7 as proposed; matching the carried todos' ticket ids took a live parallel session's book, review R-F001).

## Three designs

- `today`: the code at `04f083a`.
- `decided`: today plus the boss's decisions on issues #2 to #8, read as the code would build them. A verify records the working trees of the loop's repositories and counts while they are unchanged, as child checks do (`treesField`, `loopTrees` in `pi/book.ts`), instead of by its order against edit entries; while a child the loop started has no result, the turn-end notice neither judges nor continues. #3, #4, #5 and #8 change nothing on these paths.
- `proposed`: `decided` plus the changes P1 to P8 (the constant `Fixes`). Each `without/P<n>` check is the proposed design without one change, in the family that change is for.

## Rerun

```sh
sh docs/models/loop-book/multitask/run-checks.sh                   # every check, about 2 minutes
sh docs/models/loop-book/multitask/run-checks.sh small-today ends-proposed without/P5
uv run --with pytest pytest -q tests/test_model_multitask.py
```

`run-checks.sh` needs the `statechart` user skill (`~/.agents/skills/statechart`, or `STATECHART=<path to scripts/statechart>`). It rewrites `check/<name>/chart.mmd` and `report.md`.

## Rules and results

| # | Rule | Invariant | today | decided | proposed |
|---|---|---|---|---|---|
| M1 | What passed, came back clear, or landed for a unit counts for that unit. | `Counted` | breaks | breaks | holds |
| M2 | A unit's book shows a check or a review only of that unit's current code. | `NotLent` | breaks | breaks, one more cause | holds |
| M3 | One unit's change, or its returned car, never takes another unit's check or review away. | `Isolation` | breaks | breaks | holds |
| M4 | At most one notice per unit and missing step per real change. | `OnePerChange` | breaks | breaks | holds |
| M5 | A notice never asks for a step that only a child still out can supply. | `AskOnlyOwed` | breaks | holds | holds |
| M6 | (decided #6) While a child the loop started has no result, the notice does not judge the loop. | `QuietWhileWaiting` | breaks | holds | breaks (P5 scopes it to the unit) |
| M7 | A turn that ends with a unit waiting on the coordinator asks for that kind of unit's step, whatever other units' workers do. | `OwedIsNamed` | breaks | breaks, one more cause | holds |
| M8 | The coordinator can always reach close with evidence. | `CanClose` | breaks | breaks | holds |
| M9 | A verify the tool answered ok to, with the unit's task, counts for that unit. | `AcceptedCounts` | breaks | breaks | holds |

The paths, by cause:

| Cause | Rules | Check | Replay test | Fixed by |
|---|---|---|---|---|
| A worker inherits the first unit's anchor, and only a run of the loop's anchor is adopted: MP-1002's worker's passing run does not count for MP-1002. | M1 | `small-today` | `test_a_workers_passing_run_of_its_units_anchor_counts_for_that_unit` | P2 |
| The coordinator's change to MP-1001's code is every unit's last change (today); under `decided` it changes a tree every verify recorded, and it is still every review's last change. | M1, M3 | `cross-today`, `cross-decided`, `without/P1`, `without/P3` | `test_the_coordinators_change_to_one_units_code_leaves_the_other_units_check` | P1 (checks), P3 (reviews) |
| `back` with a unit's task floors every unit. | M1, M3 | `causes/back-1` (hidden behind the edit in `cross-today`) | `test_a_returned_car_reopens_only_its_own_unit` | P3 |
| A persistent reviewer's verdict is recorded for the unit of its first brief. | M1, M2 | `cross-today`, `without/P4` | `test_a_persistent_reviewers_clear_verdict_on_the_second_unit_counts_for_that_unit` | P4 |
| `decided` only: a worker's follow-up edit in its worktree does not change the loop's trees, so its unit's check stands. | M2 | `cross-decided`, `without/P1` | none (not today's code) | P1 |
| `/reload` clears the notice's memory, and the same notice comes again. | M4 | `notice-today`, `without/P6` | `test_a_reload_does_not_send_the_same_notice_again` | P6 |
| The notice's key is the phase name and the open-todo list: another unit's progress and a todo that moves ask MP-1001 again. | M4 | `causes/spam-1`, `without/P5` | `test_another_units_progress_does_not_ask_the_first_unit_again` | P5 |
| The notice asks for the step of the first unit not done, even when its worker is out. | M5, M6 | `small-today`, `notice-today` | the rule-5 tests of `test_model_loop_book.py` | decided #6 |
| A failed result is no evidence, so a dead worker's turn is not judged. | M7 | `notice-decided`, `without/P5` | none (the agent sees the failed result) | P5 |
| A run that started a subagent ends unjudged. | M7 | `small-today`, `causes/owed-1` | none | P5 |
| The notice follows the first unit not done (one nobody started), not the unit that waits. | M7 | `causes/owed-2` | `test_the_notice_names_the_unit_that_waits_not_the_first_unit_nobody_started` | P5 |
| `decided` only: the quiet while any worker is out keeps a unit that waits for its review unnamed. | M7 | `causes/owed-3` | none (not today's code) | P5 |
| A new session starts an empty book: what the units proved is gone, and a verify with a task is answered ok and counts nothing. | M1, M8, M9 | `ends-today`, `without/P7` | `test_a_handoff_to_a_new_session_keeps_what_the_units_proved` | P7 |
| A landed notice for a branch the coordinator pushed itself is recorded `declared` and does not count. | M1, M8 | `without/P8` | `test_a_unit_the_coordinator_carried_itself_lands_through_its_car` | P8 |

## Configs

Each family is one config per design; the families keep each run under 70,000 states.

- `small-*` with `view-small.mjs`: the chart the reader confirms. Two units, a worker each, the coordinator's runs and turn ends, no failure steps; 98 states, 11 chart states.
- `cross-*` (family 1): the coordinator's own edit, a returned car, a follow-up to a returned worker, one persistent reviewer.
- `notice-*` (family 2): someone else starts a turn, a todo moves, `/reload`, a worker that dies and is started again, the persistent reviewer.
- `ends-*` (family 3): a handoff to a new session, a car that lands, a unit the coordinator carries itself, a dead worker, a declared verify.
- `without/P<n>`: the proposed design without one change. `causes/*`: hidden causes, one switched off at a time: `back-1` (no edit by the coordinator), `spam-1` (no `/reload`), `owed-1` to `owed-3` (no dying worker; then `RunWaits` off; then `P5u`, which is P5 with the decided quiet kept).

## What the model leaves out

- The single-loop causes `../LoopBook.tla` already covers: notes and other-repository writes, shell edits, a reviewer that reads while the code changes, other roles' reviews, a subagent session's own reviewer.
- Failing checks and blocking reviews: every run passes and every review is clear.
- A worker whose result never arrives (a closed pane); a cancelled worker is a failed one.
- The notice's wording and Jev's answers: "the notice asks unit X for step S" is its first line; whether it continues the run is joined with whether it speaks.
- The tower, intercom asks, forms, and late monitor wakes are one step, `Wake`: none of them writes the book.
- Joined steps: a worker's anchor run is joined with its return; sending a car and the integrator's merge are joined with sb's landed notice and the observation.
- Assumed of the coordinator (`HasStep`): it starts a unit's worker again after a failure or a returned car, runs a unit's anchor, sends a checked unit to the reviewer, and sends a car. It does not edit a unit while that unit's worker is out, and it rotates sessions only when no worker is out.
