---
name: anchorloop
description: Use when doing loop work (change, check, iterate) that no skill was named for, especially coding; every entry skill runs this loop, and its playbooks cover unattended runs, pauses, and resuming a prior run.
---

# Anchor Loop

Every entry skill (`answering`, `investigating`, `inspecting`, `coding`, `integrating`, `deploying`, `writing`, `solid-loop`) runs this loop and supplies the steps through one of its playbooks. The target project's instructions and an exact project skill govern where they speak.

## Align

Open the first reply on any task but a fully specified one-line edit, in the user's language, with:

    Alignment: <the user's goal, the problem it solves, and, when the task ships a change, the smallest change expected to meet it>

Proceed without waiting for confirmation: a misreading caught here costs one message instead of a wrong change. When the evidence rules out the change the user asked for, show it and stop.

Read the [PRINCIPLES.md](PRINCIPLES.md) index, and open an entry whenever its trigger fires, at Align or later in the run, since a principle fires only when read. Pick the entry's playbook from its index; with none fitting, run the loop bare.

`todo` holds real work items only, optionally with `metadata.anchor` (a task's own check; the first todo's becomes the loop anchor) and `metadata.ref` (`<path>#<heading>`). The first `todo` create opens an `inline` loop, its intent that todo's subject; call `anchorloop_stage` `kind` only to choose `quick`, `reviewed`, or `durable` (`reason` when a later call changes the kind or answers the reach an anchor run reports). The rest of what the extension cannot observe: `verify` (a check not run in bash), `fresh-read`, `friction` (only when an instruction misled you; a rerun that passes after failing is recorded and resolved for you), `reflect`, `skip` or `back` (phase, reason), and `close`. Edits, anchor runs, reviews, and spec files are read from evidence; a phase that starts before an earlier one is complete warns once (`read` if you disagree), and `close` refuses only while an open todo lacks `metadata.followup` (a ticket id, `memory`, or `drop — <reason>`). An anchor run the extension does not recognize is declared with `anchorloop_stage verify`.

## Anchor

Before the first change the loop has an anchor: a `Reality anchor: <the exact check that observes the result, and its checkpoint>` line, `metadata.anchor` on the first todo, or `anchor` on a `kind` call.

A check written or changed for this run is run once red before its green counts: on the pre-change tree, or on a broken variant of new code, red for the stated reason (not an import or fixture error), because a check seen only green proves nothing. An existing suite or validator the change does not edit counts as it stands. The anchor's definition (test, fixture, baseline, validator, threshold) belongs to whoever the brief names; an anchor edited during the run is reported with its diff, and a changed expected value needs evidence that the expected behavior changed, otherwise stop and ask. Raising a budget, adding an allowlist or ignore entry, skipping or xfailing a test, and disabling or soft-failing a check are gate changes, not fixes: name each in the reply with its reason for the user to accept, and when the change-set has a review anchor, put it before that reviewer too, because the author is the one who wants green.

Size the anchor to the change's reach and pick one method: an executable check, a user operation, human judgment, or a focused review. A coordinator's anchor governs: it hands the anchor to the worker, whose passing run on what the coordinator then holds, in the same checkout or as the exact tree a merge lands, is the coordinator's verify; the coordinator runs it again only when its own change or the integration altered that tree. Pick a review anchor when the change touches a shared contract, authorization or permission data, a migration, or security; other changes rest on their check and the author's own read of the diff. A review anchor names the realistic use it judges against and blocks on P0 and P1 findings only, recording lower ones as follow-ups.

Handle findings from a review, or from a bot's or person's comment on the change, by [review-findings](references/review-findings.md). The checkpoint is normally once, after the last increment.

## Act

Work in the smallest useful increments through the project's native practices, deleting before adding ([**Subtract before you add**](principles/subtract-before-you-add.md)).

Make a small fix you hold full context for yourself; delegate units of work; the session that holds the request keeps the loop (anchor, todo, and reply). Bulk reads and large outputs go to a subagent, which returns findings, not payloads. When you delegate, coordinate subagents, or remove a worktree, follow [delegation](references/delegation.md). Write briefs, follow-ups, and messages to agents by [agent-terse](../agent-terse/SKILL.md); read each subagent's output and write its summary yourself.

Report problems outside the contract as follow-ups (siblings of the root cause being fixed are inside it), because each extra fix reopens review on code the round never touched.

The reply names a [principle](PRINCIPLES.md) only with the decision it changed.

### Friction Notes

An anchor that passed, failed, and passed again is recorded and reflected as resolved by the extension. Record `anchorloop_stage friction` yourself only for a failure whose cause a later attempt revealed, or when an instruction misled an attempt (`led_by`).

### Decision Trail

A run the user reviews after stepping away keeps a decision trail in `scratch/decisions-<task-slug>.tsv` through the `anchorloop_decision` tool, by [decision-trail](references/decision-trail.md).

## Verify

Exercise the anchor and report what it observed. A requirement the anchor did not exercise is `unknown`, whatever other checks show. Report local tests, builds, interactive runs, commit, push, CI, merge, and deployment as separate claims; one never stands in for another, and CI or PR state is re-queried before it is reported. Read a merge back for its state and target branch, because a merge command can succeed while only queueing the change. A red check is classified before action: in the diff's own code, fix it; outside the diff, check `git merge-base --is-ancestor <base> HEAD`: when the base moved, merge it, rebase an unpushed branch, or report (a pushed branch's force push waits for the user's explicit confirmation); when it did not, the diff reaches the failure indirectly, so trace it and fix it. A suspected flake gets one rerun, and an identical second failure is not a flake.

Observe the real artifact ([**Prove it works**](principles/prove-it-works.md)) through the user's path, not internal setters or test-only endpoints, and check its side effects (files written, rows inserted, messages sent); a dry-run's real effects are observed, not assumed. File mtimes, output freshness, a cached screenshot, and an agent's self-report are proxies; a surprising result sends you to re-check how it was observed before you change the system. Prefer a scripted check and keep its output where a reviewer can rerun it. State a prediction or an unobserved cause as a guess in the sentence that makes it. Run every check you can, and hand the user only one you cannot, saying why. A criterion that needs human judgment is a human checkpoint: propose a `human-feedback` pass when it is still `unknown`, and record its verdict apart from executable or review evidence.

A review anchor stays open until an independent reviewer returns its verdict. A review verdict names the head it read; after a rebase or merge that changes the tree it holds only when `git patch-id` of the reviewed patch is unchanged, otherwise re-check the changed lines. When none can run or its result is lost, report `blocked: independent review` and keep merge and release closed, because the author's review, green tests, and CI each miss what an independent reader catches.

Write the reply the playbook's `Reply:` line names, opening with one line restating the user's goal, then the playbook's lead, and carrying the anchor's evidence. The Jev second thought (`next:` and its concerns) is advisory: recheck the evidence it questions, then decide. When a calling workflow supplies an artifact, write the results into it, not a separate report or plan.

### Reflexive Pass

Run only when the book holds friction; otherwise say nothing. Classify each entry with `reflect`: **misdirection** when the `led_by` line states or implies something `found` contradicts; **gap** when no instruction in use states the `found` fact. A gap the change itself resolved, or a tool slip no instruction owns, is `resolved`. Invoke `solid-loop` with the rest.

**Complete when:** every requirement has evidence from its anchor or is reported `unknown`, and every friction entry is applied through `solid-loop` or reflected as resolved.

## Playbooks

- [autonomous-run](playbooks/autonomous-run.md): the user steps away and the run drives to a predicate without them.
- [pause](playbooks/pause.md): an explicit pause, going offline, a restart, or imminent compaction.
- [pickup](playbooks/pickup.md): resuming or taking over a prior run's work.

Lifecycle playbooks wrap the entry playbook.

---

Playbooks, principles, and the decision trail are adapted from [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT License), revision `e44668c`, with the engineering-standard additions of 2.8.0 from [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack) revision `c742dd6`.
