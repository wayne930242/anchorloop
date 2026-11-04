---
name: answering
description: Use when explaining a concept or how something works, comparing technical alternatives, summarizing results or a change for the user, or when the user says they do not follow (看不懂, show me, 講清楚一點).
---

# Answering

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is that every material claim carries its source and its evidence grade as `investigating` defines them; gather missing evidence through `investigating` first.

Keep prose brief and state uncertainty where it lives: a prediction or an unobserved cause is a guess, labeled in the sentence that makes it. Cite only what you opened this session, because the user trusts a cited claim; a link, `file:line`, ID, or quote a subagent relayed and you did not open is labeled `asserted (via <agent>)`, and one nobody read stays out. Use the exact symbol, file, flag, or command name, one name per concept.

Show the shape beside the sentence it supports, with the smallest view that makes the point: a call tree or file tree for structure, pseudocode for logic, `A → B: message` lines for interaction, a table for options against criteria. Give three or more parts as a series where each view adds one part, because one view of all of them reads as reference, not understanding. State a point plainly instead of announcing it (*key insight*, *tricky part*).

## Playbooks

- [explain](playbooks/explain.md): how something works, what changed, or what a result means.
- [compare](playbooks/compare.md): choosing between alternatives.

---

The views are adapted from HumanLayer's [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me) (MIT, © 2026 HumanLayer).
