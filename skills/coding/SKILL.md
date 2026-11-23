---
name: coding
description: Use when changing source code or its tests, such as fixing a bug, adding or changing behavior, refactoring, improving performance, or prototyping a design question.
---

# Coding

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md) with one of the playbooks below. Return to the goal line when user intent or observable behavior changes, and name in the reply any behavior the requirement leaves open.

## Anchor

Point the anchor at what the change touches: a one-line edit anchors on the tests that assert that file; a shared code path or a changed export anchors on its callers' tests and the repository's tree-wide checks (lint, config sweeps, ratchets, changelog checks); a behavior users see (config keys, output, notices, flags) anchors on a check of that output. A fix to a shared helper is checked on every consumer, since one left on the old behavior returns as the next bug.

When the project has no runnable way to drive the surface, building one (launch from an empty state, drive, evidence, cleanup) is the first change, and the reply lists each setup step a stand-in environment did that the target will not. When one change carries several fixes, give each fix a test case only it turns green, and check that reverting that fix alone turns its case red.

## Review

A change the loop sends to review (authorization or permission data, a migration, a shared contract, security) writes three to five premises before the first edit: where its results land, what names may contain, how paths are spelled, what a second run or a crash halfway leaves behind. Execute the load-bearing premise against the real code, and look for readers a symbol grep cannot see: JSON an API returns, a database column, a wire format, another language reading the same bytes, a feature flag. The reviewer's brief carries the premises and asks it to test each against the code, sweep each finding's class across the change, and report every issue it can prove in one pass. Repros run in a disposable worktree copy, never in the reviewed checkout.

## Spec first

When the user asks for a spec, or a user-owned trade-off, material ambiguity, or cross-component coordination blocks the design, follow [MINI-SDD.md](MINI-SDD.md) before any production edit.

## Playbooks

- [bug-fix](playbooks/bug-fix.md): broken, failing, slow-for-a-reason, or intermittent behavior.
- [feature](playbooks/feature.md): new or changed behavior, or an interface that crosses a module.
- [refactoring](playbooks/refactoring.md): structure changes, behavior does not.
- [perf](playbooks/perf.md): a measured slowness to improve against a baseline.
- [prototype](playbooks/prototype.md): disposable code that settles a design or behavior question.
- [state-model](playbooks/state-model.md): a flow with several actors, retries, restarts, or timeouts, checked as a TLA+ model whose bug paths become red tests.

## References

- [Benchmark checklist](references/benchmark-checklist.md): the measurement checks `perf` runs before reporting a number.
- [Design red flags](references/design-red-flags.md): the shape screen `feature` runs on a new interface.
- [State model checks](references/state-model-checks.md): the config sizing and `statechart` notes `state-model` reads.
