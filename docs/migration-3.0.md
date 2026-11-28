# Migrating to pi-anchorloop 3.0.0

3.0.0 removes the turn tax: the loop book and its phase machine, the stage and decision tools, the Jev second thought, the anchor gate, and the stream rules.
The loop is one rule: write `Anchor: <check>` before the first edit, show a passing run of it after the last change, and send a change that touches authorization or permission data, a migration, a shared contract, or security, or any work two or more workers carried, to one fresh-context reviewer (since 3.3.0, any model family), where P0 and P1 block the merge.

## What changed

| Gone | Replacement |
| --- | --- |
| `pi/book.ts` and `pi/support/` (book, phases, units, landing, links, orphans, pushes, snapshot, host), the status widget, books under `~/.pi/agent/anchorloop/` | `pi/close-guard.ts`: one line at settle when files changed with no passing anchor run since; it reads the session branch and keeps no files. |
| The kinds `quick`, `inline`, `reviewed`, `durable` | The one rule above; `coding` keeps a premises step for reviewed changes and `MINI-SDD.md` for work whose spec comes first. |
| `anchorloop_stage` (`kind`, `verify`, `fresh-read`, `friction`, `reflect`, `skip`, `back`, `landed`, `close`, `read`, `resume`) | No tool. The anchor is the `Anchor:` line or a todo's `metadata.anchor`; a non-bash check is reported in the reply; a landing is read from git. |
| `anchorloop_decision` and `scratch/decisions-<slug>.tsv` | The `autonomous-run` playbook appends plain lines to `scratch/decisions-<slug>.md`. |
| `pi/second-thought.ts` (`anchorloop-second-thought` messages) | None. |
| `pi/anchor-gate.ts` | The close guard's "no `Anchor:` line" notice. |
| `pi/ttsr.ts` (stream rules from `~/.pi/agent/rules/` and `.pi/rules/`, `/ttsr`) | None in this package; see below. |
| `PRINCIPLES.md`, `principles/`, `references/decision-trail.md`, `references/delegation.md`, `references/review-findings.md`, `coding/references/reviewed.md` | Folded into the loop card (`skills/anchorloop/SKILL.md`) and `coding/SKILL.md`. |
| Resume by book id (`pause` wrote it, `pickup` passed it as `resume`) | The resume note carries the anchor and each unit's status; `pickup` restates the anchor. |

Kept: every skill name, the three lifecycle playbooks, the merge-train contract version 1 of `integrating` and `deploying`, `pi/validate-tool-use.ts`, and the Python validators.

## What references it elsewhere

This inventory records the references at the 3.0.0 migration, not the current state of these repositories.

Read at pi-straw-boss `94d5523c` and weihung-basic-agent `3c0be5b`.

### weihung-basic-agent

- **Stream rules lose their enforcer.** Nine rules carry a `condition` and were enforced only by `pi/ttsr.ts`: `rules/no-broad-pkill.md:3`, `rules/no-env-dump.md:3`, `rules/no-extract-onto-root.md:3`, `rules/no-git-add-all.md:3`, `rules/no-git-stash.md:3`, `rules/no-pipe-tail-in-chain.md:3`, `rules/no-ps-command-line.md:3`, `rules/no-tail-follow-grep.md:3`, `rules/no-timeout-without-kill.md:3`. Move `ttsr.ts` into the agent root as its own extension before pinning 3.0.0, or these commands stop being blocked.
- `scripts/lesson-audit.mjs:21-53` loads `pi/ttsr.ts` from the anchorloop package and throws when it is missing; `tests/stream-rules.mjs:6-22` depends on it.
- `AGENTS.md:16`, `README.md:28`, `tests/pi_steps.py:44`, and `skills/reflecting-to-root/SKILL.md:27` name anchorloop's TTSR extension as the stream-rule enforcer.
- `rules/session-rotation.md:3` and `pi/AGENTS.unattended.md.in:99`: the handoff carries "the loop's book id (the `book:` line of `anchorloop_stage read`)" and the new session "passes the book id as `resume` on its first `anchorloop_stage kind`". Replace with the resume note's anchor and unit status.
- `pi/AGENTS.unattended.md.in:24`: "run `anchorloop_stage verify` with `task: <todo id>`" after a train's merge. Replace with recording the merge sha and train in the todo or the reply.
- `skills/going-to-sleep/SKILL.md:19,28` route to the `autonomous-run`, `pause`, and `pickup` playbooks, which remain.
- `scripts/pi_root/pins.py:130`, `tests/pi_fresh_machine.py:13`, and `tests/pi_packages.py:38,52,65,103,116,122` pin `npm:pi-anchorloop@2.18.1`.

### pi-straw-boss

- `src/reviver.ts:148`: the revive prompt says "resume the loop's book id it names". No book id exists now; the handoff names the anchor instead.
- `src/cut.ts:23-24`: `WAKES` lists `anchorloop-second-thought` as a turn-starting custom message; harmless but dead. `tests/restored.test.ts:817-818` pins that entry.
- `tests/items.test.ts:13` uses a `ttsr_injection` custom entry as a hidden item; harmless.
- `prompts/planning.md:9` writes `metadata.anchor` on a todo, which the close guard still reads; no change needed.
- `src/train/contract.ts:15` requires `integrating` and `deploying` to declare `merge-train-contract: "1"`; both still do.
