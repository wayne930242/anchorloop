# Design red flags

The next contributor may be an agent that sees only the files it opened and copies the nearest example. Screen a new shape for these before building it; each one lets an edit that is right in one file be wrong across the repo.

- **Shallow module.** The interface is nearly as complex as what it hides. Callers learn the internals anyway.
- **Information leakage.** Transport, storage, or wire types appear in the public surface ([**Boundary discipline**](../../anchorloop/principles/boundary-discipline.md)). Callers come to depend on the encoding.
- **Temporal decomposition.** Modules named for phases (load, validate, transform, save) repeat the same domain rule in each. Split by what changes together.
- **Pass-through.** A layer forwards its arguments and adds nothing. Delete it.
- **Split ownership.** More than one module writes the same state. Give each actor its own state and merge at the read boundary ([**Separate before serializing shared state**](../../anchorloop/principles/separate-before-serializing-shared-state.md)).
- **Two ways to one task.** Two entry points reach the same outcome, so the next agent picks the wrong one. Keep one and delete the other.
- **Importable internals.** A module's private parts can be imported from outside. Make an outside import fail the build.
- **Hand-synced list.** Two lists must change together. Derive one from the other, or make the build fail when they disagree.

A shape that survives the screen is the one where the same edit made from one file stays correct repo-wide, with drift caught by the build, not by prose.

---

Adapted from pstack `architect` (`references/design-red-flags.md`) by Lauren Tan (MIT License), revision `c742dd6` of cursor/plugins.
