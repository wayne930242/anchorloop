# How anchorloop's extensions work

The full behavior behind the [README](../README.md). The skills tell an agent how to work; the two pi extensions below catch what is cheap to catch in code, and neither starts a turn or registers a tool.

| Extension | What it does | Section |
| --- | --- | --- |
| `pi/close-guard.ts` | Adds one line when a run settles after a file change with no passing run of its anchor since. | [The close guard](#the-close-guard) |
| `pi/validate-tool-use.ts` | Validates skills, instruction files, and specs after each edit. | [Validators](#validators) |

## The close guard

The one claim worth checking in code is the last one a run makes: that the check it named passed on the tree it leaves behind.
When a run settles, `pi/close-guard.ts` reads the session branch and, if a file changed after the anchor last passed, adds one short line to the session.
The line is shown in the transcript and reaches the model with the next prompt; it never starts a turn.

<details>
<summary>What counts as the anchor, a change, and a passing run</summary>

The anchor is the last labelled check line (`Anchor:`, `Reality anchor:`, `Gate:`, `Gates:`, `Check:`, `Checks:`, `Verify:`, `Verification:`, `Done when:`, `檢查：`, `驗證：`, `驗收：`; bold, list, and heading markers also count; a label other than `Anchor:` counts only when its line holds a backticked command) in the brief, meaning the first user message, or in the agent's text, or the last anchor on a `todo` call, whichever came later. The guard reads the call first, then each `tasks[]` item in order, taking the first non-empty string from `anchor` and `metadata.anchor` at each step, or else the `metadata.sb.spec.check.run` of a straw-boss check spec.
Each backticked command in the line is one check; a task anchor without backticks is one command as written.
An anchor with no command, such as a reviewer's verdict or a person's acceptance, is not judged.

A change is a `write` or `edit` that succeeded; prose (`.md`, `.txt`, `.rst`) written after a code change does not move the last change, so a report or changelog written after the check does not undo it.
A run of a check is a `bash` call, or a monitor started with `MonitorCreate` once its outcome arrives, whose command contains the check's text, with runs of spaces collapsed, so `uv run pytest -q tests/` counts for `pytest -q`.
A run passes when its exit code is 0; a `todo` call that records passing `evidence` after the last change counts as a passing run of each check its `command` contains, until a later run of that check replaces it.

The guard speaks when files changed and either no anchor was stated and no passing evidence was recorded since, or some check's latest run came before the last change or failed.
The line names the checks still missing, for example:

```text
anchorloop: no passing run of `pytest -q` after the last change.
```

The guard reports missing checks once, then stays quiet until the todo list changes: further edits alone do not bring the line back, while a todo update, such as completing a task, does, even when nothing else changed since the last line.
It also stays quiet while the anchor's todo waits, that is, while the todo whose `anchor` or straw-boss check spec named the anchor is open and has `metadata.waitsOn` set or a `metadata.until` still ahead (pi-todo-ledger's `waitsOn` and `until` fields; `until` counts only as an ISO date or date-time with a `T` on a real calendar day, the form the ledger and straw-boss accept); for an anchor stated in text, while every todo in progress waits, unless a todo was completed after the last change.

With pi-todo-ledger installed, the guard also names the task whose anchor passed and asks the agent to append any unrecorded runs with `todo update`: one `evidence` item per run, with `command`, `result: "pass"`, and `sha` when known.
The guard identifies the task from the accepted call and the branch’s `todo/v1` snapshot; it judges the run from the bash result, never from the ledger.
For this reminder, each check must pass as written after the last edit (a simple `cd dir &&` or `uv run` prefix also counts); a command that only prints the check or masks its failure supplies no evidence.
The same run gets one reminder, visible on the next prompt; only the agent can write the ledger.
Everything is read from the branch, so a resumed or reloaded session reads the same state.

</details>

## Validators

Skill and instruction files drift in small ways that are cheap to catch the moment they are written.

<details>
<summary>What is validated, and where the rules live</summary>

After each `write` or `edit`, `pi/validate-tool-use.ts` validates the file in-process (`pi/support/validators.ts`, a port of `hooks/validators/`).
It appends suggestions for `SKILL.md` (at most three red-line advisories per edit), instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `rules/`), and `docs/specs/` artifacts.
It needs no Python.
The Python validators in `hooks/` remain for `validate_all.py` and the parity test.

</details>
