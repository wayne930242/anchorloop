# Train

**You own the train from departure to the pushed merge.** One train is assembled, reviewed, gated, and merged once; a dropped car is a local rebuild, and nothing is force pushed.

1. **Depart** when the train reaches `maxCars` (default 4), or its oldest car has waited `maxWaitMin` (default 60), or every coordinator awaited has arrived (with the default handoff route, none is awaited), and the project skill's `Load` allows it (omitted: wait while the 1-minute load exceeds the core count), and the integration branch's pipeline is not red. A red branch departs only a fix-forward car ([urgent-car](urgent-car.md)).
2. **Assemble** on a local `train/<code>` from the latest base, in a worktree `train-<code>`: `merge --no-ff` each car in arrival order. Resolve a plain conflict and log it in the ledger; a semantic conflict goes back to the later car. Then run `Train assembly`.
3. **Review.** A fresh-context reviewer ([inspecting](../../inspecting/playbooks/diff-review.md)) reads `train/<code>` against the base for interactions between cars, conflict resolutions, and migration order. P0 or P1 of one car goes back to that car; of the assembly, you fix it.
4. **Gate.** Run `Full gates` once per train, at the load `Load` allows. Green: push `pre-dev/<code>` (only now), run `Merge`, then `Post-merge`. Read each post-merge pipeline's conclusion, not that its monitor finished, because a finished run can be a failed one.
5. **Red.** `Full gates` says how to find the guilty car and which failures are flakes to rerun once. Drop the car and rebuild from the rest. Tell its coordinator: car, failing tests, log path, and the `train` SHA; the coordinator hands over a new SHA. When its session is gone, escalate `blocked`.
6. **Re-run on every head change.** A dropped car, or a post-push `git revert -m1` of a car's merge commit, makes a new head: it goes through `Train assembly` again, the reviewer rechecks it from a delta brief (what changed since the verdict, and the verdict's head), and `Full gates` runs again; after a revert, all of this precedes `Merge`.
7. **Hand on.** Carry the merged train through the remaining `stages` ([SKILL](../SKILL.md#stages)), then [After the train](../SKILL.md#after-the-train).

**Reply:** the train `<code>`, its cars with SHAs, conflicts resolved, the review verdict with the head it read, the `Full gates` result on the merged head, dropped cars with their evidence, and the merge read back (state and target branch).
