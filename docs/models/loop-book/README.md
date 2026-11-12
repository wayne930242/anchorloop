# Loop book model

A TLA+ model of one loop book as the agent meets it: what the book counts as the last change, the check and the review after it, post-landing observations, linked subagents, the turn-end notice, and close. It lives beside the code because the loop book is a long-lived flow: a change to `pi/support/phases.ts`, `pi/support/book.ts`, `pi/support/units.ts`, `pi/support/landing.ts`, `pi/book.ts`, or `pi/second-thought.ts` edits `LoopBook.tla` first and reruns the checks.

The rules are proposed (2026-11-12); the reader, the person who decides how a loop should behave, has not confirmed them yet.

A coordinator that runs several units at once, each with its own worker, has its own model in `multitask/` ([README](multitask/README.md)): what one unit's steps do to the other, and the turn-end notice while workers are out, for today's code, the decided fixes, and the changes proposed on top of them.

## Rerun

```sh
sh docs/models/loop-book/run-checks.sh            # every check, about 90 s
sh docs/models/loop-book/run-checks.sh small full # some of them
uv run --with pytest pytest -q tests/test_model_loop_book.py
```

`run-checks.sh` needs the `statechart` user skill (`~/.agents/skills/statechart`, or `STATECHART=<path to scripts/statechart>`). It rewrites `check/<name>/chart.mmd` and `report.md`.

## Rules and results

| # | Rule | Invariant | Result | Report |
|---|---|---|---|---|
| 1 | A check that passed stays passed until something the anchor tests changes, or you take it back. | `KeptDone` | breaks, 3 causes: a file written in another repository, a note git ignores, a worker's edit in its own worktree | `check/full`, `check/causes/kept-1`, `kept-2`; holds with the three off (`kept-3`) |
| 2 | A verify the tool answered ok to counts. | `AcceptedCounts` | holds with one unit (`check/held`); breaks with two units that have their own anchors | `check/units` |
| 3 | A review that came back `Blocking: P0=0 P1=0` after the last change counts as the review. | `ReportedReviewCounts` | breaks, 2 causes: the subagent's role is not `reviewer`; the session is itself a subagent | `check/full`, `check/subsession`; holds with both off (`causes/reported-1`) |
| 4 | A loop can always be finished complete with evidence. | `CanFinish` | breaks, 2 causes: an observation in a session that linked no subagent (no ref is watched, so no landing is recorded); a reviewed loop in a subagent session | `check/full`, `check/inline`, `check/subsession`; holds with observations off (`causes/finish-1`) |
| 5 | While a subagent the loop started has not returned, the turn-end notice does not judge the loop. | `QuietWhileWaiting` | breaks, 2 causes: someone else starts the next turn; another subagent's return starts it | `check/full`, `causes/quiet-1`; holds with one subagent and nobody else (`quiet-2`) |
| 6 | The book never shows the check as passed for code that changed after it ran. | `NoStalePass` | breaks: a change through a shell command | `check/full`; holds with shell edits off (`causes/stale-1`) |
| 7 | The book never shows a review as clear when the code changed while the reviewer was reading. | `ReviewReadTheChange` | breaks, 2 causes: an edit while the reviewer reads; a shell edit while it reads | `check/small`, `causes/read-1` |
| 8 | Close never needs phase evidence: once every todo is done or has a followup, close is accepted. | `CloseNeedsOnlyTodos` | holds (822,400 states); breaks when `Close` is made to need a complete loop | `check/held` |

Each broken rule has replay tests in `tests/test_model_loop_book.py`, red on the code this model describes.

## Configs

- `small.cfg` with `view-small.mjs`: the chart the reader confirms. A reviewed loop, one reviewer, the anchor and the review may fail; 162 states, 7 chart states. It compares states by `NoTurnView`, since with no turn end in the config the two turn flags decide nothing.
- `full.cfg`: every step on, in a main session with one unit. The command stops each run at 100,000 states after the first break, so `held.cfg` checks the rules that run left unfinished, without the bound.
- `units.cfg`, `subsession.cfg`, `inline.cfg`: the shapes of a session a constant decides (two units with their own anchors; a session that is itself a subagent; an inline loop with an observation).
- `causes/*.cfg`: one cause switched off at a time, until the rule holds.

## What the model leaves out

- The anchor phase, the durable phases (decide to design), `quick` loops, friction and reflect.
- How a bash command is recognized as a run of the anchor, and a run whose exit reads `unknown`.
- Units beyond "a declared verify with no task counts for no unit": per-unit reviews, landings, and observations are in `multitask/`.
- Landings other than your own push with a ref watched: a worker's branch landing, adopted runs, a push that is not the checked tree.
- What Jev answers. The model has only "the notice judged the loop or did not"; the wording of concerns and whether an advisory repeats are outside it.
- Joined steps: a write is its call and its result in one step; starting a subagent and its link are one step; a reviewer's return and the review entry are one step.
- Assumed of the agent (`SomebodyHasAStep`): it does not use `skip` as evidence, and it does not start a subagent only to get a ref watched.
