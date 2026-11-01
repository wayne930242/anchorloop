---
name: coding
description: Use when changing source code or its tests, such as fixing a bug, adding or changing behavior, refactoring, improving performance, or prototyping a design question.
---

# Coding

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md) with one of the playbooks below. Return to Align when user intent or observable behavior changes.

## Classify

Before the first production edit, classify the change by what it reaches, not by how settled the approach feels:

- **Inline:** the change stays inside the files it edits: no export another file uses, no behavior its users are told about, and no behavior the requirement leaves open. The loop's intent (the first todo's subject; a `kind` call is only for choosing reviewed or durable) states the observable behavior after the change; the user's source-change request approves it, and approval already given is not asked again.
- **Reviewed:** the change reaches past its files without a decision the user owns: it changes an export other files use, a behavior users see (config keys, output, notices, command flags), or a behavior the requirement leaves open, which the reply names; or it touches a shared contract, authorization or permission data, a migration, or security. Before the first edit, write its premises in the todo's `metadata.premises`: three to five lines on what the change assumes holds, such as where its results land, what names may contain, and how paths are spelled. It needs no spec and no further approval.
- **Durable:** the work needs a persistent design record because of material ambiguity, a trade-off the user owns, cross-component coordination, migration risk, or a user-requested spec. Read [MINI-SDD.md](MINI-SDD.md) and create or resume its folder, which keeps no `tasks.md`; Spec waits for the user's approval before any production edit.

Re-classify when the reach changes: the user adds scope, an anchor run reports the diff's reach, or the change turns out smaller. Call `kind` with a `reason` naming the kind that now fits, or why the current one still fits. Verified work carries over; an upgrade adds only the new kind's phases, the premises and review for Reviewed, and for Durable the record from decide on, with the code so far as prototype evidence.

## Anchor

Point the anchor at what the change touches: a one-line edit anchors on the tests that assert that file; a shared code path anchors on its callers' tests and the repository's tree-wide checks, such as lint, config sweeps, ratchets, and changelog checks. When one change carries several fixes, give each fix a test case that only it turns green, and check that reverting that fix alone turns the case red: a case two fixes both satisfy stays green when either is reverted. For Inline work, a green anchor plus a read of your own diff completes Verify; report the contract with its observed output in one line. Reviewed work adds an independent review whose brief carries the premises and asks the reviewer to test each premise against the code, to sweep each finding's class across the change, and to confirm the tree-wide checks ran. Durable work verifies into `verification.md` as MINI-SDD describes.

## Playbooks

- [bug-fix](playbooks/bug-fix.md): broken, failing, slow-for-a-reason, or intermittent behavior.
- [feature](playbooks/feature.md): new or changed behavior, or an interface that crosses a module.
- [refactoring](playbooks/refactoring.md): structure changes, behavior does not.
- [perf](playbooks/perf.md): a measured slowness to improve against a baseline.
- [prototype](playbooks/prototype.md): disposable code that settles a design or behavior question.
