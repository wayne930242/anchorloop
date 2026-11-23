---
name: inspecting
description: Use when auditing or reviewing a specific target, diff, commit, or spec, or running final QA or a release-readiness check.
---

# Inspecting

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is that every scoped item has a verdict and its evidence. When a reviewer role contract is present, it governs scope, evidence, and report format; add only the Standards and Spec axes.

## Playbooks

- [diff-review](playbooks/diff-review.md): a branch, pull request, worktree, or change set.
- [qa-release](playbooks/qa-release.md): final exploratory QA or release readiness.

Any other target runs the flow below directly.

## Inspection Flow

1. **Scale.** A narrow target or claim is inspected directly; several clear items get a short checklist first; security, production, destructive effects, or unclear boundaries get a plan presented first, waiting for confirmation only in a review the user started directly. Cover only the relevant dimensions (correctness, edge cases, architecture, security, performance, conventions, dependencies, side effects). Take the blocking severity and the use to judge against from the assignment; without them, judge realistic use, and count a rare edge case as blocking only when it loses, silently overwrites, or corrupts data.
2. **Verify.** Give each item a verdict (pass, fail, needs attention, or insufficient evidence) and its evidence, graded as `investigating` defines. For a change judged safe, name the one fact its safety rests on and take it to `executed`.
3. **Report.** Lead with the conclusion, then a `Check Item | Verdict | Evidence` table, failures first by impact. Name any unverified boundary. Count the findings you rejected or could not reproduce, each with its reason; zero findings is a valid result, stated as such.
