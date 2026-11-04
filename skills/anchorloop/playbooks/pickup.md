# Pickup

**You own the resume point.**

1. Locate the prior trail: the resume note, the decision trail, the branch, and this workspace's pi sessions only (the cwd's folder under the session directory: `~/.pi/agent/sessions/--Users-me-proj--/` for `/Users/me/proj` unless `--session-dir`, `PI_CODING_AGENT_SESSION_DIR`, or `sessionDir` moves it). Parse a long session in a subagent and keep the reduced timeline.
2. Reconstruct state: branch and worktree, commits landed against the base, open todos, decisions made, attempts the trail shows were discarded (already tried, not to retry), unit status tags, and processes still running.
3. Treat the trail as authoritative: name the resume point, record a `start` row with your run id in any decision trail you continue ([decision-trail](../references/decision-trail.md)), and redo nothing it shows finished.
4. Route the remaining work to its entry playbook, which owns the rest of the run; the outcome is one of continue the execution, ship a finished recommendation, ratify or override a prior conclusion, or postmortem a failed run.
5. Before reporting done, verify the inherited claims against the original goal on the real artifact; a prior self-report is not the proof.

**Reply:** where the prior run stopped, what was inherited and what was redone, the resume point, and the outcome.
