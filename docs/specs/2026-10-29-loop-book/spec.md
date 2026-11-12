Status: approved
Approved at: 2026-10-29
Approved from: user replies 2026-10-29 00:2x–01:0x (「同意」 v1; v2 notes; v3 「可以」 with the spec-file note below)

# Spec: loop book

An agent declares where its anchorloop loop stands with one tool; the extension attaches evidence, keeps one YAML book per open loop, and gives the Jev second thought the book's intent, diff summary, and verify state instead of excerpts of the request and reply. Gates exist to make work easier: a missed stage warns, never blocks, except closing a loop with undisposed todos.

## Behavior

### Loop lifecycle

- No open loop: nothing is gated or recorded; the anchor gate and the second thought stay silent. Simple work runs without ceremony.
- The first `todo` create while no loop is open opens a loop and its book. The todo tool result gets one appended line telling the agent to declare the loop kind. A `todo` create while a loop is open extends that loop.
- Only one loop is open per session. A second `kind` declaration on an open loop changes (upgrades) its kind; it never opens a new loop.
- `close` is manual. It refuses while any `pending` or `in_progress` todo lacks `metadata.followup` set to a ticket id, `memory`, or `drop — <reason>`, and lists those todos. On success it appends one custom session entry (intent, kind, verdict, stages, review rounds, diff summary, followups), deletes the book file and its child books, and tells the agent to clear the todo list.
- A new loop cannot open until the open one is closed.

### Loop kinds and their stages

| Kind | Use | Stages expected |
|---|---|---|
| `quick` | config, typo, small tweak | `act`, `check`, `close` |
| `inline` | clear scope, finishes this run | `anchor`, `act`, `verify`, `close` |
| `reviewed` | shared contract, authorization or permission data, migration, security | `anchor`, `act`, `verify`, `review`×N, `close` |
| `durable` | MINI-SDD | `decision`, `spec`, `design`, then as `reviewed` |

Any stage accepts `skip: <reason>`. Missing stages produce warnings, not refusals:
- `inline`/`reviewed`/`durable`: a `write` or `edit` outside the anchor-gate exemptions before an `anchor` stage warns once (the existing anchor gate, now active only inside an open loop; the `Reality anchor:` line also counts as the anchor stage).
- `durable`: a production edit while the spec's `Status:` is not `approved` warns once.
- `reviewed`/`durable`: two consecutive review rounds with blocking findings warn: stop and hand the trend to the user.

### Tool `anchorloop_stage`

| Call | Agent supplies | Extension attaches |
|---|---|---|
| `kind` | kind, one-line intent | base `HEAD` of the session cwd's repo; repos of later edited paths are added with their `HEAD` at first touch |
| `anchor` | the check (command or review) | — |
| `act` | optional note | diff stat against each base |
| `check` / `verify` | optional note | exit code and last output line of the latest bash call whose command contains the anchor command; `unknown` when none ran |
| `review` | optional note | round number; P0/P1 counts from the latest reviewer result's `Blocking: P0=<n> P1=<m>` line, else a Jev yes/no on blocking findings |
| `decision` / `spec` / `design` | optional note | see Durable artifacts |
| `close` | `landed`, `blocked`, or `abandoned` | todo check, diff summary, review rounds |
| `read` | `summary` (default) or `all` | about five lines: kind, stages done, last verify, review rounds and trend, open children |

In a subagent (`isSubagent()` in `pi/second-thought.ts`), the book lives under the child's `PI_SUBAGENT_ID` and a declared `verify` is recorded as `check`; only main records `verify` and `review`. Main links a child book when its `subagent` tool result returns the child id, and `read` includes each linked child's summary.

### Friction and reflection

Agents write their own mistakes and friction into the book, so the reflexive loop reads one source:

- `anchorloop_stage friction` with `tried`, `found`, and `led_by` (the skill or instruction line that prompted the attempt, or `none`) appends a numbered `friction` entry. Main and subagents both write it; a child's friction shows in main's `read` and in the Jev state under its child id.
- The book records failed attempts automatically: each anchor, check, or task-anchor run keeps its exit code, so a fail later followed by a pass is visible as a `retry` pair without any agent call.
- `anchorloop_stage reflect` with `friction` ids, `class` (`misdirection`, `gap`, or `resolved`), and `action` (e.g. `solid-loop`, `memory`, a commit) appends a `reflect` entry.
- Second thought adds two next-stage choices: `friction` when the book shows a `retry` pair with no friction entry after it, and `reflect` when friction entries lack a `reflect`. Both are advisory.
- `close` does not refuse over friction. Its session entry carries every friction entry with its reflect class, so the record survives the book's deletion, and its result lists unreflected friction for the Reflexive Pass.
- The Friction Notes section of `skills/anchorloop/SKILL.md` points to `anchorloop_stage friction` instead of `scratch/friction.md`; the Reflexive Pass reads the book's friction entries.

### Todo links

Inside an open loop, each `todo` create or update is recorded as a task entry carrying its id, subject, status, and these `metadata` keys when present:

- `anchor`: the task's own check (command or review); a task without one inherits the loop anchor.
- `ref`: one or more `<path>#<heading>` pointers into a spec, design, or other doc. The book resolves each heading to its current line range when recording (`spec.md#Second thought → L88-L101`) and re-resolves at `read`; a heading that no longer exists shows `missing`.
- `followup`: as in Loop lifecycle.

The Jev state includes this task list with a one-line legend (`#id status subject — anchor (last exit) — ref → line range; missing = heading gone`), so Jev can judge each task's own anchor and spec coverage.

`read` lists each task as `#id status subject — anchor — refs (line ranges)` and, when a bash call matched a task's own `anchor`, its last exit code. A task in an `inline`, `reviewed`, or `durable` loop without `anchor` or `ref` is recorded as is; no warning. The skill text mentions the keys once, as optional, in a clause where `todo` is introduced (e.g. "a todo may carry `anchor` or `ref` in its metadata when its check or source differs from the loop's"); it does not ask agents to fill them, because the second thought catches missing coverage. `followup` is named only in the close rule.

### Durable artifacts recorded automatically

A successful `write` or `edit` to `docs/specs/*/{decision,spec,design,verification}.md` inside an open loop appends an entry with a brief content summary, without any agent call:
- `decision.md`: row counts by status (`grounded`, `confirmed`, `open`) and the questions of rows whose status changed since the last entry.
- `spec.md`: its `Status:` value and the headings whose text changed.
- `design.md`, `verification.md`: headings whose text changed; for `verification.md`, pass/fail/unknown counts.

Repeated edits during grilling produce one entry each, so the book shows the spec converging.

### Book file

Valid YAML at `~/.pi/agent/anchorloop/books/<project-slug>/<book-id>.yml`, children under `agents/<PI_SUBAGENT_ID>.yml`. A header written once (book id, owner, session file, kind, intent, bases), then `entries:` with one flow mapping per line, each appended with a single `O_APPEND` write. Kind changes and new bases are entries, never header rewrites.

`session_start` deletes books whose owner session file no longer exists and child books linked to no open book, and lists the deletions; open books of live sessions stay and are listed.

### Second thought

- Runs only while a loop is open: when a run settles and the book gained an entry since the last judgment, and at a `close` declaration.
- Sends Jev only `kind`, `intent`, `anchor`, `diff` (≤1200 chars), `verify` (stages, review rounds, child checks), and `todos` (open count) from the book. The `checkpoint` question is removed.
- Its main output is a **next-stage suggestion**, a choice question: `continue` (keep acting), `verify`, `review`, `fix`, `close`, or `ask-user`. `done` asks whether the verify evidence covers the intent; `review` asks which review the diff still needs given the recorded reviews; `quality` is unchanged.
- The advisory message to main leads with the suggestion, e.g. `Second thought: next → close (verify pass after last change, review r2 clear, 0 open todos)`. It is advisory; it continues the run only when the suggestion is `verify`, `review`, or `fix` and the book shows that stage missing after the last `act`, once per run.
- When a review is recorded after the last `act`/`fix` with no open blocking finding, a `full` rating shows a note and does not request a recheck.

### Skill text trims

- A: delete the rule that a Jev `full` rating forces a review anchor; review anchors come from the explicit list or the user, and Jev's tier is advisory.
- B: `Alignment:` and `Reality anchor:` are required only inside an open loop.
- C: `todo` holds real work items only; stop copying playbook steps with `skip:` lines; stage progress lives in `anchorloop_stage`.
- D: feature playbook's four throughput todos only when dispatching parallel workers.
- E: a small fix that main holds full context for is made by main; larger follow-up rounds go to a fresh subagent.
- F: drop "continuity across sessions" from the Durable threshold; the book and `pickup` carry continuity.
- Unchanged: the fresh-reader spec check in MINI-SDD.

## Non-goals

Blocking any tool besides `close`; recording stages without a declared loop; changing `anchorloop_decision`.

## Reality anchor

`uv run --with pytest pytest -q` with new tests covering: todo-opens-loop and extend; kind upgrade; close refusal listing undisposed todos and success deleting books plus the session entry; evidence attachment from bash exit codes; `Blocking:` parsing; durable artifact summaries across repeated edits; subagent verify recorded as check and child linking; second-thought state built from the book, silence without a loop, recheck suppression; stale-book sweep; YAML validity under parallel appends. Plus `uv run python hooks/validate_all.py .`. Then one fresh-context reviewer, because the second thought's judging interface changes.

## Amendment: phase machine (user approved 2026-10-29, all recommended choices)

The design in `phases.md` (this folder) is binding, summarized here:

- Every loop kind runs a fixed phase sequence: `quick` act → check → close; `inline` anchor → act → verify → close; `reviewed` adds review before close; `durable` decide → grill → spec → read → approve → design → anchor → act → verify → review → close.
- Each phase has an entry condition (the previous phase complete or skipped) and a completion condition read from book evidence: decide = `decision.md` has rows; grill = 0 open rows (auto-skipped when there were none); spec = `Status: proposed`; read = a dispatched subagent whose brief contains the spec path returned after proposed (fallback: `anchorloop_stage read`); approve = `Status: approved` with `Approved from`; design = `design.md` approach section non-empty; anchor = `Reality anchor:` line or anchor stage; act = production diff; verify/check = anchor command exit 0 after the last act; review = a round after the last act with `Blocking: P0=0 P1=0`; close = todo followups (the only refusal).
- Acting in a phase whose predecessor is incomplete warns once per jump, naming what is missing and the `anchorloop_stage skip <phase> <reason>` escape. Skips are recorded and shown in the close summary.
- Phases regress when evidence changes (spec back to proposed, a diff after verify), and the next jump warns again.
- The anchor gate, the durable approval warning, and the two-rounds-blocking warning become phase-machine checks, not separate mechanisms.
- The program computes the next phase; `read` shows `<kind> · phase <current> ✓ → <next> (missing: …) · skipped: …`. Jev's state gains `phase` (current, next, missing) and Jev judges only whether to advance, go back, or ask the user; phase completion comes from the program's evidence alone (2.2.2).

## Amendment: friction in the phase machine, Jev read detection, manual regression (user 2026-10-29)

- Friction and reflection join the phase machine: every kind gains a `reflect` phase just before `close`. Entry: the previous phase complete or skipped. Completion: every `friction` entry (own and linked children's) has a `reflect` entry. Auto-skipped when the loop has no friction. Closing with unreflected friction is a phase jump: it warns once, never refuses; the todo followup rule stays the only refusal.
- `read` (goldfish) detection: a manual `anchorloop_stage read` completes the phase and skips detection. Otherwise, when a dispatched subagent returns after the spec became proposed, Jev judges from its brief and result whether it was a fresh-context read of the spec (restated contract, listed guesses); the brief containing the spec path is a pre-filter, not the verdict.
- Manual regression: `anchorloop_stage back <phase> <reason>` moves the loop back to that phase; later phases count as incomplete until their completion conditions hold again, and the entry is recorded and shown in the close summary.

## Amendment: lean surface (user 2026-10-29: "務必確保流程能精簡")

The agent declares only what the program cannot observe; everything observable is derived from evidence. This amendment overrides earlier sections where they conflict.

- Declarations: `kind` (kind, intent, optional `anchor` command; calling it again upgrades kind or sets the anchor, e.g. once a durable design is done), `verify` (only for an anchor that is not a command: human judgment or a user operation, with a note), `fresh-read` (manual goldfish completion, replacing the manual `read` of 2ea9f84 so `read` stays the query), `friction`, `reflect`, `skip`, `back`, `close`, and the query `read`. Nothing else is accepted.
- Derived, never declared: act (write/edit/commit), check/verify for a command anchor (exit code of a bash call containing the anchor command, or a task's own anchor), review rounds (reviewer results), decide/grill/spec/approve/design (spec files), read (Jev detection), retry pairs.
- Inside an open loop the `kind` call replaces the prose `Alignment:`, `Inline — Contract:`, and `Reality anchor:` lines: intent is the alignment and contract, `anchor` the reality anchor. A `Reality anchor:` line still counts when written, so existing briefs keep working. Outside a loop nothing is required.
- `quick` has no phase warnings; its only prompt is the close reminder.
- Every warning and second-thought message is one line, once per phase jump or judgment; a repeated identical one is suppressed.
- Skill text gets shorter: the Align and Anchor ritual lines, the `Inline — Contract:` line in coding, and the Friction Notes format block are replaced by one paragraph naming the declarations. `skills/anchorloop/SKILL.md` and `skills/coding/SKILL.md` must end shorter than at 9034242.

## Amendment: 2.2.3 follow-ups (user 2026-10-29)

- The skill no longer promotes `anchorloop_stage read` as a routine step; it names `read` once, for when an advisory and the agent's view disagree. `Status: approved` stays self-written; no approval check is added.
- A child that closed its loop and opens another keeps the closed book as `<id>.closed-<n>.yml` beside the new one; main's `read` lists both (`name~n` for the earlier loops) and main's close or the sweep removes them with the child.
- A run counts only where its exit can be the call's: not inside `$(`, `<(` or `>(` (except the whole of `x=$(run)`); an `||` or `!` before any enclosing group makes the exit unknown. Unrecognized is the fail-safe outcome.
- TTSR: a match that blocks a tool call ignores the repeat policy; reminders and prose injections keep it. Rule text renders literally.

## Amendment: evidence per tree and per unit, the notice per unit (user decisions 2026-11-12, issues #2 to #8 and #10 to #16; 2.16.0)

The decisions on the issues the loop book models found (`docs/models/loop-book/`, `docs/models/loop-book/multitask/`) override earlier sections where they conflict. The replays in `tests/test_model_loop_book.py` and `tests/test_model_multitask.py` hold each rule.

### Checks and reviews

- A check counts while the code it ran on is unchanged (#2, #7). Every anchor run (a `verify`, a child's `check`, a task anchor's `taskrun`) records `treeAt`: the repo root its command ran in (the session's checkout, moved by a leading `cd`; for a worker run adopted for its unit, the worker's worktree) with that repo's working-state tree. The run stands while that tree is the working tree now and no later `edit` names that repo or names none. A write in another repository, a worker's edit in its own worktree, and a file git ignores (which is no `edit` at all) leave it; a change through a shell command voids it. A run with no `treeAt` (a declared verify, a book written before 2.16.0) stands until any later change, as before.
- `edit` entries carry the `repo` they touched; consecutive edits in one repo stay one entry, and a write to a file git ignores is not recorded.
- A review counts from its reviewer's dispatch (#8): the review entry names the `link` or `send` it answers (`from`) and the trees that dispatch gave the reviewer (`treeAt`, recorded for reviewer roles). It stands while no change follows the dispatch and those trees hold. Only `reviewer` and `adversarial-reviewer` results are review rounds (#4); a subagent session records its own reviewers' rounds, and no other subagent result.
- With two or more units, `verify` without `task` is refused and the refusal lists the units with their task ids (#3).
- A `verify` with `checkpoint` that names no observation of the loop says which todo lists observations and to give `task` (#5).

### Units

- A unit's trees are its non-reviewer workers' repos (their worktrees, or the checkout they work in), else the loop's own repos. An `edit` counts for the units whose trees hold its repo, and for every unit when none does or its repo is unknown; a unit compares only its own trees, so one unit's change never takes another unit's check away (#11, P1, P3).
- `back` and `skip` with `task` reach only that unit, and `phase` is checked against that unit's kind (#11).
- A child bound to a unit inherits that unit's anchor (task entries now record `kind`, `lands`, and `agents`, so the child reads the unit from its parent's book). When the child returns, its latest passing run of that anchor, made after its last edit, is recorded as the unit's verify with the run's `treeAt` (#10).
- Each `subagent_send` or `subagent_resume` to a linked child is a `send` entry bound to the unit its brief names by ticket; a reviewer's verdict counts for the unit of the dispatch it answers, else the unit its result's brief names, else the unit its child is bound to (#12).

### Landings

- A loop that lists an observation (on its anchor or on a todo) watches its own repo's integration ref even with no linked child; a plain session with neither still makes no landing git calls (#5).
- A bash call that may push (`git … push`) in a loop that watches refs lists the remote-tracking refs of its own repos around it; a ref git shows moved by this checkout's own push is a `push` entry (a car), bound to the unit its name names by ticket. When the integration ref takes it, the landing counts for that unit, and `landed` with `task` takes it as a candidate too (#16).

### The turn-end notice

- A run that called `MonitorCreate`, `LoopCreate`, or `goal_wait`, or a subagent tool whose child the book has not linked yet, is waiting and is not judged. A dispatch is out until a result of that child follows it.
- One unit's loop (fewer than two units): while any child is out, the loop is neither judged nor continued (#6); otherwise as before.
- Two or more units (P5, the comment on #6, #13): a child out for no unit keeps every unit quiet; a child out for a unit keeps only that unit quiet. The notice takes the first unit that waits on the coordinator (its todo open, its phases not complete, nothing of its own out, and started: a child bound to it, or an edit or landing of its own) whose step it has not asked since that unit's evidence last changed. It judges, speaks, and continues for that unit (Jev's state is that unit's phase, check, and review), and names every other such unit on its own `next:` line. A unit is asked again only when its step or its evidence count changes; a child's result, failed or not, is evidence of its unit. When every unit is done or closed, the loop is judged whole as before.
- What the notice judged and said is kept in the book as `notice` entries, keyed by unit and step and that unit's evidence count (or by the loop's evidence count and open todos, with the advisory key sent), so a `/reload` rebuilds nothing and repeats nothing (#14).

### Sessions

- A handoff names its book through the todos it carries (#15): when a main session with no book of its own creates its first todos (or declares a `kind` whose intent names a ticket) and exactly one open main book of another session of this project has an open todo naming one of those tickets, the session adopts that book. The file moves to this session's path with this session's file in its header, and an `adopt` entry names the book it came from; what the units proved and what the notice asked carry over.

### Book format

New entry stages (`send`, `push`, `adopt`, `notice`) and fields (`treeAt`, `repo`, `from`, `task` on reviews, landings, and skips, `kind`/`lands`/`agents` on task entries) are additions. A book written by an earlier version loads and reads as it did: runs without `treeAt` and edits without `repo` fall back to order, task entries without unit metadata give a child its parent's loop anchor, and a book without `notice` entries is judged as new.
