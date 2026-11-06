---
name: integrating
description: Use when reviewed work is ready to enter a shared integration branch alongside other work, such as batching branches into a merge train, assembling and gating a batch, merging a car to develop or main, handling a red integration branch, or taking an urgent or fix-forward car.
---

# Integrating

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is that the full gates passed once on the exact head that was merged, the review of that head holds P0=0 and P1=0, every car's approval is quoted, and the merge reads back with the integration branch as its target.

Several authors' reviewed branches (cars) enter the integration branch as one train: one assembly, one review of the result, one run of the heavy gates, one merge. Each author's gates stay light, because full suites run per car repeat the same minutes on code the train runs again.

## Seams

Read [seams](references/seams.md) first. It names the six seams a host binds (handoff route, batch owner, approval, record, escalation route, settings) and the default of each. Everything below says "the owner", "the approver", "the ledger", and "escalate", and the bound or default mechanism answers each.

## Principle

A car's anchor before handoff is its review (P0 and P1 clear), behaviour tests aimed at its own change, and the project skill's `Light checks`. Format, lint, build, full type-check, full suites, publish, and similar gates run once, by the owner, on the assembled head. The project skill may name exceptions. Where `stages` include `uat`, a `human` anchor is the train's UAT: the slip names its checkpoints file and the author shows the approver nothing itself. The train replaces the author's merge-time checkpoint, not its fresh-context review.

## Project skill contract

The project skill holds every concrete check, found by these headings exactly as written; add nothing it does not say.

| Heading | Read by | Holds |
|---|---|---|
| `## Light checks` | coordinator | The checks to run before handoff and how to report them. |
| `## Train assembly` | owner | Project steps after the cars are merged and before the gates (migration reordering, snapshots). |
| `## Full gates` | owner | The heavy checks, which depend on the clock (run at low load), how to find the guilty car on red, and which failures may be rerun as flakes. |
| `## Merge` | owner | How the train enters the integration branch. |
| `## Post-merge` | owner | What to watch after the merge, how to confirm the release, who closes tickets. |
| `## Deploy` | owner | Stage `deploy`: how the train reaches each target, in what order, what a target needs beyond the slip's `auth`, how a failed one is rolled back. |
| `## Deploy verify` | owner | Stage `deploy`: what shows a target runs the train's own version. |
| `## UAT` | coordinator, owner | Stage `uat`: which cars carry checkpoints, where and how the deployed result is captured and by whom, and whether a commented car is reverted before its fix. |
| `## Urgent lane` | owner | Optional: when a car may jump the queue, and whether it may interrupt a running gate (an urgent car does not, unless this says so). |
| `## Load` | owner | Optional: the project's lock name and load thresholds. |

`Light checks`, `Full gates`, and `Merge` are required, and so is each heading of a declared stage (`deploy`: `Deploy` and `Deploy verify`; `uat`: `UAT`). When one is missing, the owner does not depart and escalates `blocked` naming the config error, because a guessed section runs checks nobody chose.

## Rules

- The owner cannot create the approver's authorization: it merges nothing whose car lacks a quote of words that cover the integration branch. A deploy target is `auto` or `strict` by the settings' `targets` (unlisted: `strict`); an `auto` target takes every train, a `strict` one only cars whose `auth` names it.
- Only the owner merges into the integration branch and claims `pre-dev/<code>`. Its own merges, pushes, and merge-triggered deploys need no further announcement, since the slips' `auth` covers them; a deploy it starts itself is announced through the escalation route naming the target, so another session sharing that target sees a clash.
- The owner keeps the ledger and one `todo` per train.

## Stages

A train runs the app's `stages` in order:

1. `merge`: [receive-car](playbooks/receive-car.md) for each arrival, then [train](playbooks/train.md) through `Merge` and `Post-merge`. An urgent or fix-forward car takes [urgent-car](playbooks/urgent-car.md).
2. `deploy`: the `deploying` skill, with the train's slips and ledger as input.
3. `uat`: the UAT stage of `deploying`, which runs the `human-feedback` uat playbook on the deployed result.

## Playbooks

- [receive-car](playbooks/receive-car.md): a car slip arrives, or the author builds one.
- [train](playbooks/train.md): departure, assembly, review, gates, red handling, merge, post-merge.
- [urgent-car](playbooks/urgent-car.md): a car that jumps the queue, and the fix-forward car for a red integration branch.

## After the train

When a car has no stage left, tell its coordinator through the handoff route: "landed in `<version>`, your commit is `<sha>`", adding "accepted in UAT" for a `uat` car. The coordinator closes its ticket; the owner does so only when the coordinator's session is gone. When the queue is empty, no stage runs, and no UAT page waits, escalate `idle` and let the host close the owner.
