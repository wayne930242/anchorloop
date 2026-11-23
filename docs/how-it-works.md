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

The anchor is the last `Anchor: <check>` line the agent wrote (`Reality anchor:` and bold markers also count), or the last `metadata.anchor` on a `todo` call, whichever came later.
Each backticked command in the line is one check; a `metadata.anchor` without backticks is one command as written.
An anchor with no command, such as a reviewer's verdict or a person's acceptance, is not judged.

A change is a `write` or `edit` that succeeded.
A run of a check is a `bash` call whose command contains the check's text, with runs of spaces collapsed, so `uv run pytest -q tests/` counts for `pytest -q`.
A run passes when its exit code is 0.

The guard speaks when files changed and either no anchor was stated, or some check's latest run came before the last change or failed.
The line names the checks still missing, for example:

```text
anchorloop: no passing run of `pytest -q` after the last change.
```

It speaks once per change: a later settle with no new change adds nothing, and the next change arms it again.
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
