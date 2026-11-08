# Decision: a loop book that tracks a coordinator

## Outcome and actors

A main session that only coordinates (workers write every line, the coordinator lands their branches and observes the result) gets a loop book whose phases move on real evidence: worker edits and anchor runs, landings by any route, post-land observations, per-ticket state, and children that lost their parent. anchorloop keeps working with no delegation host and with any host; pi-herdr-agents is reached only through a small adapter; no Straw Boss code or prompt changes.

## Scope

In: `pi/book.ts`, `pi/second-thought.ts`, `pi/support/{book,phases,snapshot}.ts`, the new `pi/support/{host,landing}.ts` and `pi/support/hosts/`, the skill text listed in `spec.md`, the README Extensions row, tests, and the version bump to 2.12.0.

Out: any edit to `pi-herdr-agents`, `pi-straw-boss`, or the main checkout; a push, publish, or tag; new recognition of anchor command forms (`AGENTS.md` freeze until 2026-11-18); parsing `git push` out of bash.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| D1 Parallel tickets | Units inside one book: a todo with `metadata.anchor`, `observe`, `kind`, `lands`, or `agents` is a unit; phases are computed per unit | boss 2026-11-08 「D1 一本 book 內分單位」 | confirmed |
| D2 Landing evidence | Watch git ref state plus the `landed` declaration; no `git push` parsing | boss 2026-11-08 「D2 看 ref 狀態＋`landed` 宣告 (no git push parsing)」 | confirmed |
| D3 Landing by another owner, not identical to the worker's checked tree | The worker's pre-merge run stands; no rerun on the integrated head | boss 2026-11-08 「D3 不重跑，採用 worker 的」 | confirmed |
| D4 Child books | Every pi-herdr child opens its book from its first change or anchor run, no todo needed | boss 2026-11-08 「D4–D7 全部照建議，現在做」 | confirmed |
| D5 Binding a child to a unit | `metadata.agents` names it; fallback on the ticket id in the child's name or brief when exactly one open todo matches | boss 2026-11-08 「D4–D7 全部照建議，現在做」 | confirmed |
| D6 `id` in pi-herdr-agents result details | Not done here; matching goes by `sessionFile`, else `name` | boss 2026-11-08 「D4–D7 全部照建議」 and the task brief: do not edit pi-herdr-agents | confirmed |
| D7 Timing | Proceed now: nothing here changes how anchor commands are recognized | boss 2026-11-08 「D4–D7 全部照建議，現在做」 | confirmed |
| Host adapter | `herdr`, `env-only`, `none`; chosen by detection, no configuration | `design.md` of the planner (seam split) | grounded |
| Prose anchors | `run` keeps today's matching; new `observe` items are closed by `verify` with `checkpoint`; a prose `Reality anchor:` line is recorded as before | planner gap 5; `phases.ts` nudge quotes prose as a command | grounded |
| Second thought | Re-judge only when an evidence entry arrives; the advisory key leaves out Jev's `move` concern | planner evidence: 14 advisories in 14 hours from a flapping `move` | grounded |
| Version | 2.12.0 in `package.json`, `pyproject.toml`, `uv.lock`, shipped as one release | task brief: prefer one release | confirmed |
