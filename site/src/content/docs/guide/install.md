---
title: Install
description: One command, plus pi-better-show for review pages.
---

anchorloop is a [pi](https://github.com/earendil-works/pi) package: skills, plus six extensions that load with them.

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

- The loop book's task records come from the `todo` tool of [`@juicesharp/rpiv-todo`](https://github.com/juicesharp/rpiv-mono/tree/main/packages/rpiv-todo#readme).
- Linking a subagent to a loop works through [pi-herdr-agents](https://github.com/wayne930242/pi-herdr-agents); pi itself has no subagents.
- The second-thought advisory needs a TypeSafe key for Jev; without one it does nothing.

Each is described where it applies, in [the extension reference](/anchorloop/reference/how-it-works/).

</details>

## Next

- [Quick start](/anchorloop/guide/quick-start/): a first task, step by step.
- [Concepts](/anchorloop/guide/concepts/): the loop and its vocabulary.
