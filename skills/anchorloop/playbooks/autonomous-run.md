# Autonomous run

**You own the exit condition.**

1. Align: state the exit condition as a predicate a command or artifact can pass or fail; a duration is not one. Also state the units remaining and the riskiest unknown, and show that sizing in the first reply (it proceeds without confirmation). Quote the user's authorization verbatim in the first trail row.
2. Anchor: the predicate is the anchor. Set the wake mechanism: `MonitorCreate` with `onDone` or `onSignal` for an event (CI, a merge, a job), a `LoopCreate` heartbeat otherwise, plus one safety deadline. Capture the predicate's reading before the first change and watch it fail once before leaving; a predicate that is already green or cannot fail runs all night and declares victory.
   Judge a delegated worker by commits, files, and processes, not its status text; after two failed retries by the same cause, drop the unit and replan.
3. Act: each iteration makes the smallest change the evidence justifies, checks it against the predicate, commits when it advanced, and discards it when it did not.
4. Act: record the decision trail by [decision-trail](../references/decision-trail.md), after a `start` row when continuing an existing trail.
5. Act ([**Never block on the human**](../principles/never-block-on-the-human.md)): fix reversible mid-run discoveries yourself in their own commits, then return to the predicate. Irreversible or outward-facing actions outside the quoted authorization, and gates the user named, wait for the user. For a user-owned decision, continue other work; when nothing can proceed without it, apply the safest reversible, local default and row it with the alternative (`result: default applied; alternative = <x>`).
6. Verify: stop when the predicate holds. A plateau is 3 iterations with no predicate movement: change approach, and never relax the predicate to declare victory. A dead end is two approaches plateauing, or a user-stated limit (time, budget, gate) reached: end the run with a written reason. Before handing back, run the trail's hand-back check.

**Reply:** the exit condition, iterations run, what landed, what was discarded, and the final predicate state, then the calls waiting on the user: for each, the question, your pick, the evidence, the risk, and what waiting costs, enough to decide from the reply alone and none cut for length.
