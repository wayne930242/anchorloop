---
title: Quick start
description: Four steps through a first task.
---

1. **Give pi a task.** Pi picks the entry skill whose description matches: `coding` for a bug fix or a feature, `investigating` for a question, `inspecting` for a review, and so on. [Skills](/anchorloop/guide/skills/) lists them all.
2. **Read the alignment.** The first reply opens with `Alignment: <your goal, the problem it solves, and the smallest change expected to meet it>`. A misreading caught here costs one message instead of a wrong change, so correct it right away.
3. **Watch the loop.** The first `todo` the agent creates opens a loop, and a widget below the editor shows `⚓ <kind> · <last complete phase> ✓ → <next phase>`. The agent states its anchor in a `Reality anchor:` line: the exact check that will observe the result. `anchorloop_stage read` shows the loop's reading in full.
4. **Read the report.** The reply carries what the anchor observed, and anything it did not exercise is marked `unknown`. Ask for a review, a human check, or a deploy when the report says one is still open.

## What you may see

- A one-line warning on an edit: the loop has no anchor yet, or a `durable` loop is missing a decision, spec, or approval. The edit still goes through.
- A `next:` advisory at the end of a turn from the second-thought extension, when Jev has a concern about the loop's evidence.
- A line asking to re-classify when a quick or inline change grew past three source files or two directories.

[The extension reference](/anchorloop/reference/how-it-works/) says exactly when each appears.

## Next

- [Concepts](/anchorloop/guide/concepts/): the loop, the four kinds, and anchors.
- [Skills](/anchorloop/guide/skills/): what each entry skill anchors on.
