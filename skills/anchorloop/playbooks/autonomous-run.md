# Autonomous run

**You own the exit condition.**

1. State the exit condition as a predicate a command or artifact can pass or fail (a duration is not one), the units remaining, and the riskiest unknown, in the first reply; proceed without confirmation. Quote the user's authorization verbatim in `scratch/decisions-<task-slug>.md`.
2. The predicate is the anchor. Watch it fail once before leaving, because a predicate already green runs all night and declares victory. Set the wake: `MonitorCreate` with `onDone` or `onSignal` for an event (CI, a merge, a job), a `LoopCreate` heartbeat otherwise, plus one safety deadline.
3. Each iteration makes the smallest change the evidence justifies, checks it against the predicate, commits when it advanced, and discards it when it did not. Judge a worker by commits, files, and processes, not its status text; after two failed retries with the same cause, drop the unit and replan.
4. Append one line per fork, pivot, discarded attempt, or blocker to the decisions file: what, why, and a pointer (commit, `file:line`, path), because a discarded attempt never reaches git log and the next run would retry it.
5. Fix reversible discoveries yourself in their own commits. Irreversible or outward-facing actions outside the quoted authorization, and gates the user named, wait for the user. For a user-owned decision, continue other work; when nothing can proceed without it, apply the safest reversible default and log it with the alternative.
6. Stop when the predicate holds. Three iterations with no movement is a plateau: change approach, and never relax the predicate. Two approaches plateauing, or a user-stated limit reached, ends the run with a written reason.

**Reply:** the exit condition, iterations run, what landed, what was discarded, the final predicate state, then each call waiting on the user with the question, your pick, the evidence, the risk, and what waiting costs.
