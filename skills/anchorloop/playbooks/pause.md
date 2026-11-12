# Pause

**You own a clean stop a cold-start agent can resume from.** Runs only on an explicit pause, going offline, a restart, or imminent compaction; "keep going" is not a pause.

1. Stop at a safe boundary: finish or back out of the current step, start nothing new, and stop the subagents and monitors you started.
2. Take no irreversible action to pause: no new push, PR, or deploy.
3. Commit uncommitted work as one `wip:` commit on the current branch, staging files by name and leaving `scratch/` and machine-local state out; when the tree is broken, say so in one line of the commit body.
4. Write `scratch/resume-<task-slug>.md`: the open loop book's id (the `book:` line of `anchorloop_stage read`), intent, each unit tagged committed and verified, uncommitted, in flight, reverted, or not started, current state, the next action, key files, and gotchas. Point to the decision trail instead of copying it.

**Reply:** where the run stopped, the `wip:` commit and whether the tree is clean, what lives only in the resume note, and the first action on resume, plus any call waiting on the user with your pick, the evidence, the risk, and what waiting costs.
