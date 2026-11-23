---
title: Quick start
description: Four steps through a first task.
---

1. **Give pi a task.** Pi picks the entry skill whose description matches: `coding` for a bug fix or a feature, `investigating` for a question, `inspecting` for a review, and so on. [Skills](/anchorloop/guide/skills/) lists them all.
2. **Read the goal line.** The first reply opens with one line restating your goal. A misreading caught here costs one message instead of a wrong change, so correct it right away.
3. **Read the anchor.** Before its first edit the agent writes `Anchor: <check>`: the exact check that will observe the result, with each command in backticks.
4. **Read the report.** The reply carries a passing run of the anchor after the last change, and anything it did not exercise is marked `unknown`. Ask for a review, a human check, or a deploy when the report says one is still open.

## What you may see

- One line from the close guard when the run settled after a file change with no passing anchor run since, such as ``anchorloop: no passing run of `pytest -q` after the last change.`` It never starts a turn.
- Validator suggestions appended to an edit of a skill, an instruction file, or a spec.

[The extension reference](/anchorloop/reference/how-it-works/) says exactly when each appears.

## Next

- [Concepts](/anchorloop/guide/concepts/): the loop rule, anchors, and the review rule.
- [Skills](/anchorloop/guide/skills/): what each entry skill anchors on.
