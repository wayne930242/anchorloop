# Fix root causes

**When:** Debugging.

Ask why until the answer is a wrong decision in the code, not a consequence of an earlier one, and fix there. Fix every place with the same fault. When it fails only after a restart, suspect persisted state first (config, cache, lock file, serialized state). Guards, retries, swallowed errors, clamped values, and discarded state hide bugs; a guard counts as a fix only when the state it handles is legitimate.
