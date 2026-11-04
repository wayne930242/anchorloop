# Make operations idempotent

**When:** A script, command, or loop that mutates state.

Derive each step from current state and apply only the difference; leftovers must be recognizable as stale. Test: run it twice, and crash it at each step, and the end state matches.
