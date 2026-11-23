---
name: solid-loop
description: Use when creating, editing, or auditing agent skills and instructions, applying friction notes, or bootstrapping or overhauling a project's agent system.
---

# Solid Loop

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is the validator, clean: the project's own validator command where it has one (in the anchorloop repository, `uv run python hooks/validate_all.py .`), else no finding appended by the `validate-tool-use` extension to the last `write` or `edit` of each edited skill, instruction, or rule file; every edited section passing the no-op test; and, when the change answers a recorded failure, a fresh-context rerun of that task in which the failure no longer occurs, or `rerun: n/a — <reason>` when no safe slice exists ([author-skill](playbooks/author-skill.md)).

The root virtue is **predictability**: each instruction sends the next run straight to the work, with no detour and no unneeded read.

## Placement

Put each fact where it stays true: every task type, the `anchorloop` core; one task type, its entry skill or playbook; one project, that project's `AGENTS.md` or `CLAUDE.md`. A multi-step procedure no skill owns becomes a playbook, or a skill when no entry fits; propose one when you meet the same workflow a second time.

## Mechanism

Enforce at the highest level that works, because nothing fails when an agent skips prose: architecture that removes the wrong path; a script for repeated deterministic work; a type, lint, or test; a tool-loop lever (pi extension hook, validator) for a check the model demonstrably skips, with a message that names the fix. Prove the check fails on the recorded mistake. A check that existing code already violates fails only on additions; the same command runs locally and in CI. Prose is for judgment calls. A fact the agent system already states in prose that a run still missed is a repeat: escalate its enforcement in the same change.

## Hold the Size

Pair each added sentence with a merge or deletion in the same file, so the file ends no longer than it began. One fact stated in several places keeps one authoritative statement; the rest become pointers or go. Keep each `SKILL.md` under 300 lines by moving reference into `references/` or a playbook.

## Craft Levers

- **No-op test**: read each sentence alone and delete the ones that do not change behavior relative to the model's default.
- **Information hierarchy**: ordered actions are steps, co-located rules are reference, templates and deep catalogs sit behind explicit pointers.
- **Leading words**: anchor behavior with compact pretrained concepts (*tight*, *red*, *tracer*) instead of spelled-out explanations.
- **Description as hook**: write the situation, in the user's own words, that should send a run here, assertively, because models under-trigger.
- **Completion criteria**: make each checkable, and demanding enough to drive thorough legwork.
- **Explain why**: put the consequence beside the rule; reserve capitals and absolutes for the one rule that causes real damage, stated once.
- **Positive steering**: state the target behavior, because a prohibition names the unwanted pattern; keep a negation only as a red line an observed failure earned, with its reason beside it. The validator flags red-line inflation as an advisory.
- **Pin derived copies**: record the upstream path and revision beside the credit of anything derived from another source.

## Playbooks

- [apply-friction](playbooks/apply-friction.md): friction notes from a run an instruction misled.
- [author-skill](playbooks/author-skill.md): creating or editing a skill, playbook, or instruction file directly.
- [bootstrap](playbooks/bootstrap.md): building or overhauling a project's agent system from investigation runs.

## References

- [Skill Template](references/template-skill.md)

---

Placement and mechanism adapted from [google-research/harness2](https://github.com/google-research/harness2) (Apache-2.0), revision `1cfe254`, `harness2/core/prompts.py`.
