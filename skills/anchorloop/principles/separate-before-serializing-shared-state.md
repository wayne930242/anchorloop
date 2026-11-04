# Separate before serializing shared state

**When:** Parallel workers, retries, or several writers of one file, key, or branch.

Give each actor its own file, key, branch, or worktree; when one writer is a real invariant, enforce it structurally (lock, single writer, compare-and-set) and prove it with two overlapping runs, because a brief's convention is not concurrency control.
