---
name: agent-terse
description: Use when writing text another agent reads rather than the user, such as a subagent brief or follow-up, a subagent's final report, an intercom, tower, broadcast, or ping message, or a scratch handoff, plan, or note only agents read.
---

# Agent Terse

An agent reader pays for every token it holds and needs no courtesy. Write for it terse like a smart caveman: cut words, never facts. Text the user reads (chat replies, questions, commits, tickets, repository docs) keeps full prose.

## Rules

1. **Point first, no ceremony.** Verdict or ask, evidence, next step. No greeting, recap, hedge, or sign-off.
2. **Structure over transitions.** `if <condition>: <action>` for branches, numbered steps for order, `key: value` for state, bullets for sets. Fragments are fine while a line reads in one pass; no invented abbreviations or arrows.
3. **Intent and acceptance, not method.** Say what must hold and how it is checked; spell out a method only where it is a constraint. A strong reader plans better than step-by-step pseudocode does.
4. **Abstract the routine, list the targets.** Name routine work as a class (`fix lint in touched files`). Give exactly each thing the reader acts on or checks: file:line, command, commit, branch, ID, port, value.
5. **Keep what flips meaning.** Every not, never, no, only, except, unless; numbers with units; code, paths, and errors verbatim; the user's authorizations and decisions quoted.
6. **Motive and reason stay whole.** Write them short but keep the cause, never a bare label like `for safety`; a reader that knows why makes the call you would where the brief is silent. The user's reasons may be restated in project terms when the cause and meaning stay the same.

## A brief stays complete

Terse cuts words inside a brief, never its fields, because a thin brief sends a subagent to redo a sibling's work or to miss part of the scope. Every brief carries:

- `goal`: the outcome and why it matters.
- `context`: the situation and the facts that change judgment (who is waiting, which environment, what an earlier round found).
- `scope`: what it owns, and what is out of scope.
- `others`: what sibling agents own or already found, so it neither repeats nor overlaps them.
- `constraints`: authorizations and decisions quoted verbatim, plus limits on method, and whether the agent may delegate further (default: it delegates nothing, because the session that holds the request keeps the anchor, todo, and reply).
- `acceptance`: the check that proves done, and the report shape to return.

A reader that finds the goal, context, or reason unclear restates its reading in one or two lines, or asks the sender, before it acts.

## Full sentences instead

Write full sentences for a security warning, an irreversible or outward-facing action, a step order a fragment could scramble, and a decision the reader must make, because a misread there costs more than every token saved.

## Before sending

1. An announcing opening or a recapping ending? Delete it.
2. Every negation, number, path, and quoted authorization still there?
3. A brief missing goal, context, scope, others, constraints, or acceptance? Add it.
4. Without the stated reason, would the reader make the same call at an edge case? If not, the reason is too thin.
5. A line with two readings? Make it a full sentence.

---

Adapted, with changes, from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (Apache-2.0, Copyright 2026 Julius Brussee), revision `bad48a0`, `plugins/caveman/skills/caveman/SKILL.md`.
