# Refactoring

**You own the behavior contract. The structure changes; the behavior does not.**

1. Anchor: from a clean trunk, pin current behavior with a characterization test, snapshot, or equivalence run before anything moves; a type check and lint are not a pin.
2. Align: name the target shape as if built today, and the branches or invalid states it deletes. A reshape that only adds indirection is not one. A redesign that changes behavior is allowed; name it and route it to `feature`.
3. Act: **Subtract before you add**, in its own commit ahead of the reshape and any follow-on cleanup, so each diff reads alone.
4. Act: move in small steps with the pin green. **Migrate callers, then delete**. Check each rename against strings, prose, and back-references.
5. Act: a bug or missing feature found on the way becomes a follow-up; the structural change ships against the pinned contract first.
6. Verify: prove equivalence on the real artifact, then confirm reader load dropped (**Minimize reader load**): a new reader answers "where does X come from?" and "what can change X?" in under 30 seconds, with state derived instead of synced; when that fails, revert.

**Reply:** the structure that changed, the pin, the equivalence evidence, the reader-load change, and what was reverted.
