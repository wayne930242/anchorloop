---
name: grilling
description: Use when resolving user-owned decisions or ambiguous architectural tradeoffs, when a decision artifact has open rows, or when the user asks to be grilled on an idea.
---

Interview the user relentlessly until you reach a shared understanding. Map the subject as a **design tree**: every decision branches into the decisions that depend on it.

When a caller hands over a decision artifact, first write every consequential question into it with the answer already supported by the request or source facts, its basis, and its status; when no row is `open`, return it without interviewing.

Work in **rounds**. The **frontier** is every open decision whose prerequisites are settled. Ask the whole frontier in one round, numbering each question and giving your recommended answer. Then wait for the user's answers before continuing.

Format each question like this:

```
❓ **Q1 — <title>**: <question and options>

➡️ <recommended answer and why>
```

Each answer reshapes the tree. Recompute the frontier before the next round. A question that still depends on another open decision belongs to a later round.

Finding facts is the agent's job. Use the environment and available tools; delegate independent fact-finding only when it materially saves time. Settle observable questions by [**Observe, don't ask**](../anchorloop/principles/observe-dont-ask.md), with a check or the `coding` prototype playbook. The decisions are the user's: put each remaining product or preference question to them and wait.

When terminology or a durable architectural decision emerges, invoke `domain-modeling` at that point.

The session is complete when the frontier is empty and every branch has been visited. Record each answer as `confirmed` in the caller's artifact, if any, and return the confirmed decisions to the caller.

---

Ported and adapted from [mattpocock/skills](https://github.com/mattpocock/skills) `grilling` and `grill-with-docs` (MIT License, Copyright (c) 2026 Matt Pocock).
