---
title: Install
description: One command, plus pi-better-show for review pages.
---

anchorloop is a [pi](https://github.com/earendil-works/pi) package: skills, plus two small extensions that load with them.

## Install the package

```bash
pi install npm:pi-anchorloop
```

That is the recommended way to use anchorloop, and it needs nothing else to run.

## Review pages (optional)

The `human-feedback` UAT playbook and `visual-designing` open their review pages with the `show_doc` tool of [pi-better-show](https://github.com/wayne930242/pi-better-show).
Install it beside anchorloop to get those pages.

```bash
pi install npm:pi-better-show
```

Without it the two skills list the screenshot or frame paths in the reply instead.

## Work from a checkout

A local checkout loads in place, so edits take effect on `/reload`:

```bash
pi install /path/to/anchorloop
```

<details>
<summary>What else the extensions use</summary>

- The close guard reads `anchor` or `metadata.anchor` from `todo`, including items in `tasks[]` and Straw Boss check specs. Install [pi-todo-ledger](https://github.com/wayne930242/pi-todo-ledger) for the reminder to record passing evidence through `todo`. Without a todo tool, use an `Anchor:` line.
- The delegation rules use a `subagent` tool, such as the one [pi-straw-boss](https://wayne930242.github.io/pi-straw-boss/docs/) provides.
- Neither extension needs a key, a model, or Python.

Each is described where it applies, in [the extension reference](/anchorloop/reference/how-it-works/).

</details>

## Next

- [Quick start](/anchorloop/guide/quick-start/): a first task, step by step.
- [Concepts](/anchorloop/guide/concepts/): the loop and its vocabulary.
