# Autonomous run

**You own the exit condition.**

1. Align: state the exit condition as a predicate a command or artifact can pass or fail; a duration is not one.
2. Anchor: the predicate is the anchor. Set the wake mechanism: `MonitorCreate` with `onDone` or `onSignal` for an event (CI, a merge, a job), a `LoopCreate` heartbeat otherwise, plus one safety deadline.
3. Act: each iteration makes the smallest change the evidence justifies, checks it against the predicate, commits when it advanced, and discards it when it did not.
4. Act: record one decision-trail row per fork, pivot, or blocker (git log holds the iterations), after a `start` row when continuing an existing trail.
5. Act: fix reversible mid-run discoveries yourself in their own commits, then return to the predicate. Bring only irreversible actions, user-owned decisions, or a real dead end to the user, and leave them in the trail when the user is asleep.
6. Verify: stop when the predicate holds. On a plateau, change approach; never relax the predicate to declare victory. A genuine dead end ends the run with a written reason.

**Reply:** the exit condition, iterations run, what landed, what was discarded, and the final predicate state.
