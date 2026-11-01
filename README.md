# pi-anchorloop

[繁體中文](README.zh-TW.md)

Agent workflow skills and loop extensions for [pi](https://github.com/earendil-works/pi). Every main task type enters through its own skill, picks a playbook, and runs one shared loop: **Align → Anchor → Act → Verify**.

## Skills

```text
anchorloop            core loop · principles · playbooks: autonomous-run, pause, pickup
├─ answering     explain · compare
├─ investigating research · diagnose
├─ inspecting    diff-review · qa-release
├─ coding        bug-fix · feature · refactoring · perf · prototype  (+ Mini SDD)
├─ writing       draft · tighten · comments
└─ solid-loop    apply-friction · author-skill · bootstrap
shared           grilling · domain-modeling · human-feedback · agent-terse
```

- **`anchorloop`** holds what is true for every task type: restate the task, pick the entry's playbook, keep real work items in `todo` (its first create opens a loop), declare the loop with `anchorloop_stage` (kind, intent, anchor command) before the first change, work in small increments deleting before adding, verify against the anchor, and record friction in the loop book. The Reflexive pass hands reflected friction to `solid-loop`. `PRINCIPLES.md` names the principles playbooks cite and the user can steer with. The lifecycle playbooks cover unattended runs, clean pauses, and picking up a prior run.
- **Entry skills** each name the anchor for their task type and index their playbooks. A playbook has an ownership line, numbered steps, and a `Reply:` line that sets what the final report contains.
- **Shared skills** are called by entries: `grilling` for user-owned decisions, `domain-modeling` for terms and ADRs, `human-feedback` for reactions to working output, `agent-terse` for text only agents read: briefs, reports, and agent messages.

## Extensions

| File | What it does |
| --- | --- |
| `pi/book.ts` | The loop book. The first `todo` create opens an `inline` loop (intent from the first todo's subject, anchor from a `Reality anchor:` line or the todo's `metadata.anchor`), and a `kind` call opens or changes one; task records need the `todo` tool of [`@juicesharp/rpiv-todo`](https://github.com/juicesharp/rpiv-mono/tree/main/packages/rpiv-todo#readme) (its `tool_result` details `{tasks, nextId}` and `rpiv-todo-state` entries). The agent declares only what the extension cannot observe with `anchorloop_stage`: `kind` (to choose `quick`, `reviewed`, or `durable`, with an intent and the anchor command; changing a kind the agent chose takes a `reason`), `verify` (a check not run in bash), `fresh-read`, `friction` (`tried`, `found`, `led_by`), `reflect`, `skip`, `back`, `close`, and the query `read`. Everything else is read from evidence: production edits (a write or edit in any git repo, outside its `scratch/` and `docs/specs/`; a linked child's edits and a successful `git merge`, `cherry-pick`, or `pull` count too), the exit code of the bash call that ran the anchor command (an anchor that passed, failed, and passed again records its own friction entry, already reflected as `resolved`: the rerun command and the failed run's key line, at most 120 characters and never a stack trace; the agent is told nothing), reviewer `Blocking: P0=<n> P1=<m>` counts, summaries of `docs/specs/*/` artifacts as they are edited, and a returned subagent that Jev judges to have been a fresh-context read of the spec. A phase machine over that evidence gives each kind a fixed sequence (`quick` act → check; `inline` anchor → act → verify; `reviewed` adds review; `durable` adds decide → grill → spec → read → approve → design; every kind ends with reflect → close), and `read` shows `<kind> · phase <current> ✓ → <next> (missing: …) · skipped: …`. A widget below the editor shows `⚓ <kind> · <current> ✓ → <next>`, with `· N friction` while friction waits for a `reflect`, after every tool call, on `session_start`, and when a `Reality anchor:` line is stated, and clears when the loop closes. An anchor run or declared verify of a `quick` or `inline` loop also measures the diff's reach: source files (not tests, lockfiles, specs, or prose), the top-level directories they sit in, and a README, changelog, or `*.schema.json` changed beside them. Files already changed when a repo joined the loop count only once their content changes, and a file at a repository root counts as a file, not a directory. At 3 source files, 2 directories, or one such file, the result carries one line asking to re-classify, and verify waits for a `kind` call with `reason` that answers each threshold crossed; a later threshold asks again. A phase that starts before an earlier one is complete warns once in one line; phases regress when evidence changes or on `back`. The book also records each todo with its `anchor`, `ref` (`<path>#<heading>`, resolved to line ranges), and `followup` metadata. One YAML book per open loop lives under `~/.pi/agent/anchorloop/books/` (`ANCHORLOOP_BOOKS_DIR` overrides it; empty project and `agents/` directories are removed), subagent books under `agents/` (a child that closes keeps its book for the main session); `session_start` sweeps books whose session is gone or that have not changed in 7 days. `close` answers `closed (landed). Clear the todo list.`, adding only the phases not shown complete and the unreflected friction, and never refuses over phases or friction, only while a pending or in-progress todo lacks `metadata.followup` (a ticket id, `memory`, or `drop — <reason>`). |
| `pi/anchor-gate.ts` | Inside an open loop, appends one warning line to the edit's tool result (where the agent reads it) when `write` or `edit` starts the `act` phase while an earlier phase of the loop kind is incomplete: no anchor (`anchor` on the `kind` call, a `Reality anchor:` line, or a skip), and in a `durable` loop a missing decision, spec, fresh read, approval, or design, read from the `docs/specs/<folder>/` files (found from the book, the intent, or a todo `ref`). It warns again only when a new phase goes missing; the call still goes through. Outside a loop and in `quick` loops it stays silent. `.md`, `.txt`, and `.html` files, `scratch/`, `docs/specs/`, and temp files outside the project pass silently. Edits made through `bash` are not checked. |
| `pi/decision-tool.ts` | The `anchorloop_decision` tool appends single-line, spreadsheet-safe rows to a decision trail TSV for forks, pivots, and blockers (completed units come from `git log`), or a `start` row when a run picks up another run's trail. |
| `pi/second-thought.ts` | Inside an open loop, asks Jev (TypeSafe's typed-decision model, through pi's classifier registry) to check the phase machine when a run settles and the loop book gained an entry since the last judgment, and at a `close` declaration. The program computes the next phase from the book; Jev sees the kind, intent, anchor, diff summary (≤1200 chars), `phase` (current, next, missing), verify state, the open todos by id and subject, the task list, and friction (a child's under its name), and judges only whether to `advance`, go `back`, or `ask-user`, plus `done`, the review tier still needed, and quality; phase completion comes from the program's evidence alone. The advisory is `next: <phase> (<missing>)` plus Jev's concerns, with no scores. It is sent only when Jev has a concern, todos are open without a followup, or the run continues, and stays silent when Jev agrees with nothing to add (the verdict is still recorded in the session); at close it carries concerns only. Away from close it also names the loop's open todos that have no valid `metadata.followup` (the first three, subjects cut to 60 characters, then `+N more`) and asks the agent to continue each, complete it, or set that followup. The run continues once, when Jev agrees to advance and the next phase is a verify, review, or fix, or when such todos are open and Jev's move is not `ask-user` (then the advisory tells the agent to ask the user instead); an advisory with the same next phase, concerns, and open todo ids as the last one is not repeated, and a `full` rating after a clean review that follows the last change is not a concern. A run that called `MonitorCreate`, `LoopCreate`, `goal_wait`, or a `subagent` tool is waiting and is not judged. Without a TypeSafe key it does nothing, and outside a loop it never runs. In a subagent session (`PI_SUBAGENT_ID` from pi-herdr-agents, or `PI_SUBAGENT_CHILD` from pi-subagents) it registers nothing, since the agent that spawned it judges the result. |
| `pi/validate-tool-use.ts` | After each `write` or `edit`, validates the file in-process (`pi/support/validators.ts`, a port of `hooks/validators/`) and appends suggestions for `SKILL.md` (at most three red-line advisories per edit), instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `rules/`), and `docs/specs/` artifacts. Needs no Python; the Python validators in `hooks/` remain for `validate_all.py` and the parity test. |
| `pi/ttsr.ts` | A port of oh-my-pi's Time Traveling Stream Rules. A Markdown rule in `~/.pi/agent/rules/` or `<project>/.pi/rules/` whose frontmatter has a `condition` regex is watched during the run. A match in streamed assistant text aborts the response, drops it, and retries with the rule injected; a match in tool arguments (the command for `bash`, the new text for `write` and `edit`) blocks the call with the rule as its reason. Frontmatter fields follow oh-my-pi: `condition`, `scope` (`text`, `thinking`, `tool`, `tool:bash`, `tool:edit(*.ts)`), `globs`, and `interruptMode` (`always`, `prose-only`, `tool-only`, `never`), plus `repeatMode` (`once` or `after-gap`) and `repeatGap`. Each injected rule arrives as `<rule name="…">body</rule>`. A rule fires once per session by default. `astCondition`, `question`, and `agents` are not supported; a rule that uses them is skipped and reported. `/ttsr` lists the loaded rules. |

## Install

Install the npm package `pi-anchorloop`; it is the recommended way to use anchorloop:

```bash
pi install npm:pi-anchorloop
```

A local checkout loads in place, so edits take effect on `/reload`:

```bash
pi install /path/to/anchorloop
```

## Develop

```bash
uv run python hooks/validate_all.py .   # skills, rules, and durable specs
uv run --with pytest pytest -q          # validators and the pi extensions (needs node)
```

## Acknowledgments

- [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT), mirror revision `e44668c` of [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack), and its port [pstack-claude](https://github.com/michael-denyer/pstack-claude) by Michael Denyer (MIT): task-type playbooks, named principles, the lifecycle playbooks, the decision trail, the closed review gate, fresh-subagent hand-off, and evidence grades.
- [google-research/harness2](https://github.com/google-research/harness2) (Apache-2.0), revision `1cfe254`: solid-loop's placement test, cheapest-mechanism order, and declining a lesson without a before/after contrast.
- [mattpocock/skills](https://github.com/mattpocock/skills) (MIT): grilling, domain-modeling, the diff review, the prototype playbook, and the feature playbook's interface checks.
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (Apache-2.0), revision `bad48a0`: the terse voice in `agent-terse`.
- HumanLayer's [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me) (MIT): the views in `answering`.
- [oh-my-pi](https://github.com/can1357/oh-my-pi): Time Traveling Stream Rules.

Ported files credit their sources in their own footers.
