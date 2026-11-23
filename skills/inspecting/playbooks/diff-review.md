# Diff review

**You own a separate verdict on each axis, measured from a fixed point.**

## Establish the evidence boundary

1. Take the fixed point the user supplied, else the configured upstream or merge target; ask only when competing bases would change the diff materially.
2. From its merge-base with `HEAD`, capture the committed range, the commit list, `git diff HEAD`, and `git status --short`, and read relevant untracked files. Stop with insufficient evidence when the ref is invalid or the change set is empty.
3. Find the governing spec: a user-supplied artifact, an issue or change reference in commits, branch-matching `docs/specs/` material, then the confirmed conversation; else report "no spec available".
4. Find the repository standards, project instructions, ADRs, and architectural precedent.

## Review independently

Keep the axes separate even when evaluated in one session.

### Standards

Find each documented-standard violation and cite its source. Tool-enforced style is left to the tool; a design smell is a judgment call, with project precedent first.

### Spec

Map each requirement to the diff and report missing or partial behavior, behavior outside the approved scope, behavior implemented incorrectly, and missing evidence for a claimed result, each pointing to its requirement. With no spec, mark this axis insufficient evidence instead of reconstructing intent from the implementation.

### Beyond the diff

Read what the diff cannot show: serialized shapes (JSON, a DB column, a wire format) and the other-language readers of the same bytes, flags, timing and teardown order, and the pinned source of each dependency the change calls, because grep stops at callers. Keep the risks you confirmed and list those you checked and cleared apart.

When a load-bearing scenario fails, run it on the base too. A failure present on both is recorded against the base and blocks only when the diff copies it or newly reaches it. When the base lacks the feature, check the behavior the diff adds, and judge a performance number by the [benchmark checklist](../../coding/references/benchmark-checklist.md).

**Reply:** separate `Standards` and `Spec` verdicts with file/hunk evidence, and a finding count and worst issue within each axis, never one combined score, because success on one axis cannot mask failure on the other.

---

Adapted from [mattpocock/skills](https://github.com/mattpocock/skills) `code-review` (MIT License, Copyright (c) 2026 Matt Pocock).
