# Delegation

Read before you hand work to a subagent, coordinate several, or remove a worktree.

Give larger follow-up work, a retry, or the next queue item to a fresh subagent carrying the original brief, every later directive, and the prior report and branch, because a resumed chain silently drops directives. Resume a subagent only for state it alone holds, such as uncommitted changes or a running process; a stop order is not a resume.

Review the worker's diff or artifact, not its report; a missing or malformed result is a gap, not a pass; account for every spawn as done, replaced, or dropped.

Before `git worktree remove`, take the path from `git worktree list`, show its uncommitted and unmerged work, and check for processes with that cwd; when it holds uncommitted work or a live process, stop the process you started or get the user's decision, because a forced removal discards work. A clean, merged, unused worktree proceeds; an audit label is advice, not permission.
