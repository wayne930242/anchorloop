---
name: solid-loop
description: Use when creating, editing, or auditing agent skills and instructions, applying friction notes, or bootstrapping or overhauling a project's agent system.
---

# Solid Loop

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is `uv run python hooks/validate_all.py .` or the project's own validator, clean, every edited section passing the no-op test, and, when the change answers a recorded failure, a fresh-context rerun of that task in which the failure no longer occurs, or `rerun: n/a — <reason>` when no safe slice exists (see [author-skill](playbooks/author-skill.md)).

The root virtue is **predictability**: each instruction sends the next run straight to the work, with no detour and no unneeded read.

## Placement

Put each fact where it stays true. One that holds for every task type goes to the `anchorloop` core; one that holds for one task type goes to its entry skill or playbook; one that holds for one project goes to that project's `AGENTS.md` or `CLAUDE.md`. A multi-step procedure no skill owns becomes a playbook, or a skill when no entry fits; propose one in the reply when you meet the same workflow a second time.

## Mechanism

Enforce at the highest level that works, because nothing fails when an agent skips prose: architecture that removes the wrong path; a script for repeated deterministic work; a type, lint, or test; a tool-loop lever (pi extension hook, stream rule, validator) for a check the model demonstrably skips, with a message that names the fix. Prove the check fails on the recorded mistake. A check that existing code already violates fails only on additions; an exception sits on its line with a reason, an expiry, and the user's approval; the same command runs locally and in CI, because a rule that differs between them makes the rule table lie. Prose is for judgment calls. A `Found` fact the agent system already states in prose is a repeat: escalate it in the same change. List each enforced rule beside its enforcer in the owning instruction file's rule table, and drop the row once the mistake can no longer happen.

## Hold the Size

Pair each added sentence with a merge or deletion in the same file, so the file ends no longer than it began. When a fix exposes one fact stated in several places, keep one authoritative statement and replace the rest with a pointer or delete them. Run the no-op test on every section you edited and delete each sentence that fails. Keep each `SKILL.md` under 300 lines by moving reference into `references/` or a playbook.

## Craft Levers

- **Information hierarchy**: Ordered actions are steps, co-located rules are reference, and templates or deep catalogs live behind explicit context pointers.
- **Leading words**: Anchor behavior with compact pretrained concepts (*tight*, *red*, *tracer*, *reality anchor*) instead of spelled-out explanations.
- **Description as hook**: Write the situation in the user's own words that should send them here, assertively, because models under-trigger.
- **Completion criteria**: Make each criterion checkable, and demanding enough to drive thorough legwork.
- **Explain why**: Put the consequence beside the rule, and reserve capitals and absolutes for the one rule that causes real damage, stated once.
- **Name the shortcut**: List the excuses the model will reach for as excuse → reality pairs, and turn adjectives into self-test questions.
- **No-op test**: Evaluate each sentence in isolation and delete the ones that do not change behavior relative to the model's default.
- **Single source of truth**: Give each operational contract one canonical home.
- **Positive steering**: State the target behavior, because a prohibition names the unwanted pattern and makes it more likely; a prohibition or discipline skill keeps a negation only as an earned red line.
- **Pin derived copies**: Record the upstream path and revision beside the credit of a skill, rule, or role derived from another source, and keep a check that fails when that upstream changes, so the derivation is redone instead of drifting.
- **Earn the red line**: Admit a red line only when an observed failure backs it (a friction note's `Found` or a bare-run failure) and its reason or excuse → reality pair rides with it; delete the rest. The validator flags red-line inflation as an advisory.

## Playbooks

- [apply-friction](playbooks/apply-friction.md): classified friction notes from a Reflexive pass.
- [author-skill](playbooks/author-skill.md): creating or editing a skill, playbook, or instruction file directly.
- [bootstrap](playbooks/bootstrap.md): building or overhauling a project's agent system from investigation runs.

## References

- [Skill Template](references/template-skill.md)

---

Placement and mechanism adapted from [google-research/harness2](https://github.com/google-research/harness2) (Apache-2.0), revision `1cfe254`, `harness2/core/prompts.py`.
