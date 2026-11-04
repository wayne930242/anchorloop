# Principles

Read this index at Align, and open an entry whenever its trigger fires, at Align or later in the run; playbooks cite entries by name, and the user steers with the same names.

## Core

- [**Subtract before you add**](principles/subtract-before-you-add.md): sizing any change.
- [**Foundational thinking**](principles/foundational-thinking.md): before writing logic or integrating a new requirement.
- [**Attack the premise**](principles/attack-the-premise.md): two fixes resting on one premise failed the same check.
- [**Minimize reader load**](principles/minimize-reader-load.md): shaping code or prose that is hard to trace.
- [**Build the lever**](principles/build-the-lever.md): any non-trivial work; skip it only for a couple of obvious edits.

## Architecture

- [**Model the domain**](principles/model-the-domain.md): logic that branches a lot or repeats a shape across files.
- [**Boundary discipline**](principles/boundary-discipline.md): wiring validation and errors, or shaping a public type or API.
- [**Migrate callers, then delete**](principles/migrate-callers-then-delete.md): replacing an API.
- [**Make operations idempotent**](principles/make-operations-idempotent.md): a script, command, or loop that mutates state.
- [**Separate before serializing shared state**](principles/separate-before-serializing-shared-state.md): parallel workers, retries, or several writers of one file, key, or branch.
- [**Type system discipline**](principles/type-system-discipline.md): any typed language.

## Verification

- [**Prove it works**](principles/prove-it-works.md): before declaring done.
- [**Fix root causes**](principles/fix-root-causes.md): debugging.
- [**Sequence verifiable units**](principles/sequence-verifiable-units.md): multi-step work and commit order.
- [**Test behavior, not implementation**](principles/test-behavior-not-implementation.md): writing or keeping a test.
- [**Observe, don't ask**](principles/observe-dont-ask.md): a question a check or prototype could answer (behavior, timing, layout, output, performance).
- [**Explain the number**](principles/explain-the-number.md): before measuring and before trusting a number.

## Delegation

- [**Never block on the human**](principles/never-block-on-the-human.md): deciding whether to proceed or ask the user.

---

Adapted from the pstack principle skills by Lauren Tan (MIT License), revision `e44668c`, with additions from cursor/plugins revision `c742dd6`.
