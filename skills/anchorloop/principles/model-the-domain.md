# Model the domain

**When:** Logic that branches a lot or repeats a shape across files.

Put the rule in one structure (state machine, table, typed model) instead of scattered conditionals. Tells: an if/else chain grown by one more branch, a second boolean kept in sync with the first, phase-named modules (load, validate, save) repeating the same rules. Prefer boring code to a forced abstraction. When the flow has several actors, retries, restarts, or timeouts, check the model exhaustively with the coding [state-model](../../coding/playbooks/state-model.md) playbook.
