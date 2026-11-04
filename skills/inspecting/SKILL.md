---
name: inspecting
description: Use when auditing or reviewing a specific target, diff, commit, or spec, or running final QA or a release-readiness check.
---

# Inspecting

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is that every scoped item has a verdict and its evidence.

When a reviewer role contract is present, it governs scope, evidence, and report format; add only the Standards and Spec axes.

## Playbooks

- [diff-review](playbooks/diff-review.md): a branch, pull request, worktree, or change set.
- [qa-release](playbooks/qa-release.md): final exploratory QA or release readiness.

Any other target runs the flow below directly.

## Inspection Flow

### Phase 1: Scale the Inspection

Choose the lightest mode that can support a trustworthy conclusion:

- **Focused:** one narrow target or claim. Inspect it directly.
- **Standard:** several clear items. State a concise checklist, then proceed.
- **High-risk or ambiguous:** security, production, destructive effects, or unclear boundaries. Present the plan; wait for confirmation only in a review the user started directly.

Include only dimensions relevant to the request: correctness, edge cases, architecture, security, performance, conventions, dependencies, and side effects. Take the blocking severity and the use to judge against from the assignment; without them, judge realistic use and count a rare edge case as blocking only when it loses, silently overwrites, or corrupts data.

### Phase 2: Verify

For each scoped item:

1. Identify the evidence that would prove or disprove it.
2. Gather that evidence directly. Invoke `investigating` only when the item requires substantial research or cross-source verification.
3. Record a verdict: pass, fail, needs attention, or insufficient evidence.
4. Grade the evidence as `investigating` defines. For a change judged safe, name the one fact its safety rests on and take it to `executed`.

### Phase 3: Report

```
| Check Item | Verdict | Evidence / Notes |
|------------|---------|------------------|
| [item] | [verdict] | [evidence] |
```

Lead with the conclusion. Prioritize failures and recommended actions by impact. Name any unverified boundary instead of implying full coverage. Count the findings you rejected or could not reproduce, each with its reason; zero findings is a valid result, stated as such, because a report of survivors alone cannot tell "found nothing" from "found five and dropped them".

