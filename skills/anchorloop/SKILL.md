---
name: anchorloop
description: Use when doing loop work (change, check, iterate) that no skill was named for, especially coding; every entry skill runs this loop, and its playbooks cover unattended runs, pauses, and resuming a prior run.
---

# Anchor Loop

Every entry skill (`answering`, `investigating`, `inspecting`, `coding`, `writing`, `solid-loop`) runs this loop and supplies the steps through one of its playbooks. The target project's instructions and an exact project skill govern where they speak.

## Align

Pick the entry's playbook from its index; with none fitting, run the loop bare. `todo` holds real work items only, optionally with `metadata.anchor` (a task's own check) and `metadata.ref` (`<path>#<heading>`). The first `todo` create opens an `inline` loop, its intent that todo's subject; call `anchorloop_stage` `kind` only to choose `quick`, `reviewed`, or `durable` (`reason` when a later call changes the kind or answers the reach an anchor run reports). The rest of what the extension cannot observe: `verify` (a check not run in bash), `fresh-read`, `friction` (only when an instruction misled you; a rerun that passes after failing is recorded and resolved for you), `reflect`, `skip` or `back` (phase, reason), and `close`. Edits, anchor runs, reviews, and spec files are read from evidence; a phase that starts before an earlier one is complete warns once (`read` if you disagree), and `close` refuses only while an open todo lacks `metadata.followup` (a ticket id, `memory`, or `drop — <reason>`).

## Anchor

Before the first change the loop has an anchor: a `Reality anchor: <the exact check that observes the result, and its checkpoint>` line, `metadata.anchor` on the first todo, or `anchor` on a `kind` call. The first edit without one gets a one-line reminder in its result.

Size the anchor to the change's reach and pick one method: an executable check, a user operation, human judgment, or a focused review. A coordinator's anchor governs. Pick a review anchor when the change touches a shared contract, authorization or permission data, a migration, or security; other changes rest on their check and the author's own read of the diff. A review anchor names the realistic use it judges against and blocks on P0 and P1 findings only, recording lower ones as follow-ups. Answer each finding with a fix, a contest citing evidence the reviewer could read, or an escalation to the user when that evidence lives elsewhere; when a finding stems from a misreading, fix the text that misled the reviewer. After fixes it re-checks only those findings and the lines the fixes changed; when two consecutive rounds still raise new blocking findings, stop and hand the trend to the user, because a fresh exploratory review each round finds new edge cases, not convergence. The checkpoint is normally once, after the last increment.

## Act

Work in the smallest useful increments through the project's native practices, deleting before adding (**Subtract before you add**).

Make a small fix you hold full context for yourself; give larger follow-up work to a fresh subagent carrying the original brief, every later directive, and the prior report and branch, because a resumed chain silently drops directives. Resume a subagent only for state it alone holds, such as uncommitted changes or a running process. Write briefs, follow-ups, and messages to agents by [agent-terse](../agent-terse/SKILL.md); read each subagent's output and write its summary yourself.

Report problems outside the contract as follow-ups, because each extra fix reopens review on code the round never touched.

The reply names a [principle](PRINCIPLES.md) only with the decision it changed.

### Friction Notes

Each time an attempt fails and a later attempt reveals why, record it with `anchorloop_stage friction` before continuing. An anchor that passed, failed, and passed again is recorded by the extension; reflect on that entry like any other.

### Decision Trail

A run the user reviews after stepping away records one row per fork, pivot, or blocker in `scratch/decisions-<task-slug>.tsv` with the `anchorloop_decision` tool; completed units come from `git log`. Evidence is a pointer (commit, `file:line`, artifact path), never prose, and a wrong call gets a superseding row instead of an edit. Before handing back, check every row against what the run did and build the report from the trail.

## Verify

Exercise the anchor and report what it observed. A requirement the anchor did not exercise is `unknown`, whatever other checks show. Report local tests, builds, interactive runs, commit, push, CI, and deployment as separate claims; one never stands in for another. A criterion that needs human judgment is a human checkpoint: propose a `human-feedback` pass when it is still `unknown`, and record its verdict apart from executable or review evidence.

A review anchor stays open until an independent reviewer returns its verdict. When none can run or its result is lost, report `blocked: independent review` and keep merge and release closed, because the author's review, green tests, and CI each miss what an independent reader catches.

Write the reply the playbook's `Reply:` line names, with the anchor's evidence. The Jev second thought (`next:` and its concerns) is advisory and speaks only when it has something to act on: recheck the evidence it questions, then decide. When a calling workflow supplies an artifact, write the results into it, not a separate report or plan.

### Reflexive Pass

Run only when the book holds friction; otherwise say nothing. Classify each entry with `reflect`: **misdirection** when the `led_by` line states or implies something `found` contradicts; **gap** when no instruction in use states the `found` fact. A gap the change itself resolved, or a tool slip no instruction owns, is `resolved`. Invoke `solid-loop` with the rest.

**Complete when:** every requirement has evidence from its anchor or is reported `unknown`, and every friction entry is applied through `solid-loop` or reflected as resolved.

## Playbooks

- [autonomous-run](playbooks/autonomous-run.md): the user steps away and the run drives to a predicate without them.
- [pause](playbooks/pause.md): an explicit pause, going offline, a restart, or imminent compaction.
- [pickup](playbooks/pickup.md): resuming or taking over a prior run's work.

Lifecycle playbooks wrap the entry playbook.

---

Playbooks, principles, and the decision trail are adapted from [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT License), revision `e44668c`. Finding triage is adapted from [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) (Apache-2.0), revision `a8380ab`, `skills/egm-resolve/SKILL.md`.
