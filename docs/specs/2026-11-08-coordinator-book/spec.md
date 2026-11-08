Status: approved
Approved from: boss decisions 2026-11-08, 「D1 一本 book 內分單位; D2 看 ref 狀態＋`landed` 宣告 (no git push parsing); D3 不重跑，採用 worker 的; D4–D7 全部照建議，現在做」, applied to the coordinator-book design of 2026-11-08 (`scratch/anchorloop-coord/design.md` in moldplan-center).

# Spec: a loop book that tracks a coordinator

## Behavior

### Host seam

- The loop book reads delegation through an adapter: `herdr` (pi-herdr-agents: `subagent` tool results with started details, `subagent_result` messages, `PI_SUBAGENT_*` env), `env-only` (pi-subagents `PI_SUBAGENT_CHILD`, avtc's `PI_SUBAGENT_CHILD_AGENT` plus `PI_SUBAGENT_PARENT_PID`: child detection only, no links), and `none`. Detection needs no configuration.
- With no host the book behaves as in 2.10.1: landings come from the session's own merges, its own pushes (ref state), and `landed` declarations.

### Links

- A link records `child`, `name`, `agent`, `sessionFile`, `cwd`, `worktree {path, branch, baseRef, baseSha}` when the host reports one, the integration ref with its SHA at spawn, and the unit.
- Spawns made before the loop opened are linked at open: the branch is walked back to the previous anchorloop close entry; a spawn whose child has a `subagent_result` after it is left out.
- A link adds a `base` for the child's repo (worktree path, else the repo of the child's cwd) at `baseSha`, so the coordinator's diff includes the worker's change while the worktree exists. When the worktree is gone, the last result's handoff stays as the diff line.
- A `result` entry `{child, failed, headSha?}` is written on each `subagent_result`.
- `read` adds an advisory line when a link's `baseSha` is N commits behind its integration ref.

### Landing

- Each link carries an integration ref, chosen in order: the unit's `metadata.lands`; the link's `worktree.baseRef` when it is not `HEAD`; the upstream of the source checkout's branch at spawn; `origin/HEAD`.
- On every bash `tool_call` the watched refs' SHAs are stored; on `tool_result`, `subagent_result`, `session_start`, and before a second-thought snapshot they are compared. When a ref moved, each unlanded link is tested by git's own equivalence in order: `merge-base --is-ancestor head ref` (rule `ancestor`); `git cherry ref head base` with every line `-` (rule `patch-id`); every path changed in `base..head` has the same blob at `ref` as at `head` (rule `content`).
- A land is recorded as `land {child, unit, ref, sha, rule, exact, self}`. `self` is true when the ref moved inside this session's own bash call (known from the SHA pair, not from parsing). `exact` is true when the ref tip's tree equals the tree of the child's latest passing check. A partial result records nothing and shows `partial k/n` in `read`.
- `land` counts as `act`. The `mergeRun` path stays for local merges. An exact land adopts the child's passing run as the coordinator's verify; a land that is not exact and `self` needs the coordinator's own run; a land by another owner (`self: false`) keeps the child's run (D3).
- `anchorloop_stage landed {sha?, ref?, task?, note?}` records an owner's landed notice and checks it with the same rules; one git cannot confirm is recorded `verified: false`, does not count, and the reply says to fetch `<ref>` first.
- No bash command text is parsed for pushes, and `anchorRun`, `anchorExit`, `locate`, `beforeRun`, `COMMAND_POSITION` and their tests are unchanged.

### Checkpoints

- A unit's or the loop's anchor is a `run` checkpoint (the exact command, as today) plus `observe` checkpoints (a list, after landing). `kind` gains `observe: string[]`; todo metadata gains `observe` beside `anchor`.
- The run checkpoint passes after the last code change and after a `self` non-exact land. Each observe item needs `verify {note, checkpoint: i}` after the last land. The missing text names the first open checkpoint (`observe 1/3`).
- An anchor that is prose has no backticks in the missing line; the nudge offers a run of its command or `verify` naming what was observed.

### Second thought

- The re-judge gate counts evidence entries only (`edit`, `land`, `verify`, `check`, `review`, artifacts, `friction`, `reflect`, `skip`, `back`, `anchor`, `kind`); `task`, `link`, `base`, `result` entries do not trigger it.
- The advisory key is `next`, the assessment findings, and the unsettled ids; Jev's `move` concern is left out.

### Child books from evidence

- In a child session, the first production edit, commit, or run of a known anchor opens its book without a todo. A known anchor is the child's own, or the run command of the parent unit that links it, found by the inverse of `findChildBooks`. Runs of that command are recorded as `check` with `trees`. The coordinator's act comes from `withChildActs`.

### Orphans

- On `subagent_result` a `result` entry is written. On `session_start` and in `read`, each link without a `result` gets one line: host liveness (`alive`, `gone`, `unknown`), the child book's state, the worktree handoff when a manifest has one. The snapshot's `verify` line carries the count. The `env-only` and `none` adapters report liveness `unknown`. Recovery stays with the host.

### Units

- A todo with `observe`, `kind`, `lands`, or `agents` is a unit, and so is the one open todo a child's ticket id binds; `metadata.anchor` alone is a task's own check and makes no unit, so a plain session with several anchored todos reads as before. A link binds to a unit by `metadata.agents`, else by the ticket id in the child's name or brief when exactly one open todo holds it; a child that matches none stays loop-wide. Phases are computed per unit over its entries plus the loop-wide ones; `read`, the widget, and the Jev `tasks` field show one line per unit. Close stays loop-level. A single-ticket loop is unchanged.

### Skill text

- `skills/anchorloop/SKILL.md` (anchor as run plus observe checkpoints, unit metadata, the `landed` declaration), `references/delegation.md` (the brief carries `Reality anchor: <run command>`; land by any route and fetch the ref before reporting landed; account for orphaned spawns), `playbooks/pickup.md` (child and unit lines are part of the reconstructed state), and `skills/integrating/SKILL.md` After the train (record the notice with `anchorloop_stage landed`).

## Release

2.12.0 in `package.json`, `pyproject.toml`, and `uv.lock`; the README Extensions row for `book.ts` and `second-thought.ts`. No push, tag, or publish in this change.
