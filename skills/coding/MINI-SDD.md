# Mini SDD

Artifacts live in `docs/specs/YYYY-MM-DD-<slug>/`, each created when its step is reached. Link to instructions, ADRs, code, and tickets rather than copying them.

1. **`decision.md`**: outcome and actors, scope in and out, concrete scenarios, and one row per consequential question. Invoke `grilling` with the file only when a row is `open`. Done when no open row blocks observable behavior.

   ```markdown
   | Question | Answer | Basis | Status |
   |---|---|---|---|
   | ... | ... | request, evidence, or decision link | grounded, confirmed, or open |
   ```

2. **`spec.md`**: observable behavior and edge cases, compatibility constraints and non-goals, evidence links, and the anchor. Have a fresh-context subagent read it, restate the contract, and list each point it would have to guess; fold each guess in or add it as an `open` row. Then ask the user. Only the user's approving reply sets the header to approved; production source stays untouched while it is `proposed`.

   ```markdown
   Status: proposed | approved
   Approved at: <date the user approved, empty while proposed>
   Approved from: <the user reply that approved it, empty while proposed>
   ```

3. **`design.md`**: the smallest approach that fits the approved spec, the interfaces and data flow it touches, precedent, and at least one rejected alternative. A flow whose rules turn on interleaving actors gets the `state-model` offer here. Done when implementation invents no product behavior.
4. **`verification.md`**: one row per requirement of `spec.md`, then deviations from the spec and open gaps.

   ```markdown
   | Requirement | Evidence | Result |
   |---|---|---|
   | Observable behavior from spec | Real interface executed and the output observed | pass / fail / unknown |
   ```

A new consequential decision returns to `decision.md`; a change to observable behavior returns to `spec.md` and the user.

---

The fresh-reader spec check is adapted from the Goldfish comprehension review in [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) (Apache-2.0), revision `a8380ab`, `agents/comprehension.md`.
