# Design: a loop book that tracks a coordinator

## Approach

The full analysis (evidence, root causes, rejected options) is the planner's design of 2026-11-08, cited at `origin/master` 72078f9; this file records what the code does.

- **Host adapter** (`pi/support/host.ts`): the interface `Host { name, isChild(env), childId(env), childSession(env), linkFrom(toolName, input, details), resultFrom(message), liveness(link) }`. `hosts/herdr.ts` and `hosts/env-only.ts` implement it; `detectHost(env)` picks the herdr adapter when `PI_SUBAGENT_ID` is set, env-only for the other child markers, and `none` otherwise. A `subagent` tool result with started details is the herdr adapter's spawn signal wherever it arrives. `pi/support/subagent.ts` becomes a re-export of `isChild`.
- **Landing** (`pi/support/landing.ts`): pure git helpers over `execFileSync`: `watchedRef(link)`, `refSha`, `landed(repo, ref, head, base)` returning `{rule}` or partial counts, `exactTree`. `book.ts` keeps one per-session map `callId -> {ref: sha}` filled at bash `tool_call` and compared at `tool_result`.
- **Book schema** (additive, readers ignore unknown fields): `link` gains `sessionFile, cwd, worktree, ref, refSha, unit`; new entries `result`, `land`, `landed` (declaration), `observe` checkpoints on `kind`/`task`; `verify`/`check` entries gain `checkpoint`.
- **Phases** (`pi/support/phases.ts`): `act` accepts `land`; `verify` computes the run checkpoint, then the observe checkpoints; units are evaluated by filtering entries by `unit` plus the loop-wide ones and calling the same `evaluate`.
- **Second thought**: `judged` counts evidence entries; a new open todo without a followup also re-judges; `adviceKey` keeps Jev's `move` beside the next phase, findings, and unsettled ids.
- **Order**: seam (WU2), links (WU3), landing (WU4), checkpoints and second thought (WU5), child books (WU6), orphans (WU7), units (WU8), skill text and release (WU9). Each unit is one commit; every new test is run red on 2.10.1 behavior before its code.

## Compatibility

Books written by 2.10.x load unchanged. A host that reports nothing leaves every new field absent and every new line out of `read`.
