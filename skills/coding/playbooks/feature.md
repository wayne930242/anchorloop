# Feature

**You own the design.**

1. Read every file the change touches and name the data shape and its organizing structure before any logic; a domain with many branches gets types that make invalid states unrepresentable. Build first what every later step leans on, such as test infrastructure and shared types.
2. When the change crosses a module, settle its interface first: write two or three real call sites and derive the signatures from them. Place the seam at an existing boundary, add one only for real variation, hide invariants and ordering behind it, make it the test surface, and validate only where untrusted input enters. Screen the shape against [design-red-flags](../references/design-red-flags.md). With no precedent and a costly-to-reverse choice, compare two shapes on depth, locality, compatibility, and testability, or settle it with `prototype`; a user-owned trade-off goes to the user.
3. For state that runs, give each actor its own state and merge at the read boundary; a lock added by reflex means the state was shared by mistake. For an operation that mutates state, ask what happens when it runs twice or crashes halfway.
4. Surface each deviation from the settled interface; when the same workaround appears a second time, reshape as if the constraint had been there from day one.
5. When dispatching parallel workers, fan out only slices that produce independent artifacts; work coupled in code (one feature, one migration) goes to one owner. For three or more near-identical units, run one through brief, report, and check before launching the rest.
6. Build in units that each end in a check, each commit passing alone. A shared primitive's improvement is ported to every consumer and verified on each.
7. Verify on the surface the user will use; an inconclusive or wrong-surface result is not a pass.

**Reply:** what was built, the shape chosen and why, the check, and open decisions; a table when alternatives were compared.

---

Interface checks adapted from [mattpocock/skills](https://github.com/mattpocock/skills) `codebase-design` (MIT License, Copyright (c) 2026 Matt Pocock).
