# Refactoring

**You own the behavior contract. The structure changes; the behavior does not.**

1. Anchor: from a clean trunk, pin current behavior with a characterization test, snapshot, or equivalence run before anything moves; a type check and lint are not a pin.
2. Name the target shape as if built today, and the branches or invalid states it deletes; a reshape that only adds indirection is not one, and one that changes behavior goes to `feature`. When the code is a flow whose states keep producing bugs, offer `state-model` as `coding` says before choosing the shape.
3. Delete first, in its own commit ahead of the reshape, so each diff reads alone.
4. Move in small steps with the pin green: migrate every caller, then delete the old path. Check each rename against strings, prose, and back-references.
5. A bug or missing feature found on the way becomes a follow-up; the structural change ships against the pinned contract first.
6. Verify equivalence on the real artifact, then that a new reader answers "where does X come from?" and "what can change X?" in under 30 seconds; when that fails, revert.

**Reply:** the structure that changed, the pin, the equivalence evidence, and what was reverted.
