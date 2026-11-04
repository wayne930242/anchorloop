# Diff review

**You own a separate verdict on each axis, measured from a fixed point.**

## Establish the evidence boundary

1. Resolve the fixed point supplied by the user. When none is supplied, use the
   clearly configured upstream or merge target; ask only when competing bases
   would materially change the diff.
2. Resolve its merge-base with `HEAD`. Capture the committed range, commit list,
   `git diff HEAD` for staged and unstaged work, and `git status --short` for
   untracked files. Inspect relevant untracked files directly. Stop with
   insufficient evidence when the ref is invalid or the whole change set is
   empty.
3. Identify the governing spec in this order: user-supplied artifact, issue or
   change reference in commits, branch-matching `docs/specs/` material, then the
   confirmed conversation. Report “no spec available” when none can be proven.
4. Identify repository standards, project instructions, ADRs, and relevant
   architectural precedent.

## Review independently

Keep the axes separate even when evaluated in one session.

### Standards

Find each documented-standard violation and cite its source. Tool-enforced style
is left to the tool. Use these smell heuristics only as judgment calls, with
project precedent taking priority:

- mysterious names and primitive domain concepts
- duplicated logic or recurring conditionals
- data clumps and feature envy
- shotgun surgery or divergent responsibilities
- speculative abstractions, pass-through middle layers, and message chains

### Spec

Map each requirement to the diff and report:

- missing or partial behavior
- behavior outside the approved scope
- behavior that is present but implemented incorrectly
- missing evidence for a claimed result

Quote or point to the governing requirement for each finding. When no spec is
available, mark this axis insufficient evidence instead of reconstructing intent
from the implementation.

### Beyond the diff

Read what the diff cannot show: serialized shapes (JSON, a DB column, a wire format) and the other-language readers of the same bytes, flags, timing and teardown order, and the pinned source of each dependency the change calls, because grep stops at callers. Keep the risks you confirmed and list those you checked and cleared apart.

When a load-bearing scenario fails, run it on the base too. A failure present on both is recorded against the base and blocks only when the diff copies it or newly reaches it. When the base lacks the feature, check the behavior the diff adds and compare no ratio between unlike scenarios.

**Reply:** separate `Standards` and `Spec` verdicts with file/hunk evidence, and
a finding count and worst issue within each axis, never one combined score,
because success on one axis cannot mask failure on the other.

---

Adapted from [mattpocock/skills](https://github.com/mattpocock/skills)
`code-review` (MIT License, Copyright (c) 2026 Matt Pocock).
