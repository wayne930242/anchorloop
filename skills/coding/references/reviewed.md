# Reviewed changes

Read before the first edit of a change classified Reviewed, and when a change is re-classified as Reviewed.

## Premises

Before the first edit, write its premises in the todo's `metadata.premises`: three to five lines on what the change assumes holds, such as where its results land, what names may contain, how paths are spelled, and what a second run or a crash halfway leaves behind ([**Make operations idempotent**](../../anchorloop/principles/make-operations-idempotent.md)). Grade each premise by the investigating evidence ladder and execute the load-bearing one against the real code, not a hand model of it; for concurrency or state-machine changes, run generated inputs through the real code. Look for readers that a symbol grep cannot see: JSON an API returns, a database column, a wire format, another language reading the same bytes, a feature flag, code three hops downstream.

## Review

The independent review's brief carries the premises and asks the reviewer to test each premise against the code, to sweep each finding's class across the change, to confirm the tree-wide checks ran, and to report every issue it can prove in the pass, because a reviewer that stops at the first one makes each round drip a new finding. Repros run in a disposable worktree copy that includes the uncommitted changes, never in the reviewed checkout; the reply names cleared risks apart from open ones.
