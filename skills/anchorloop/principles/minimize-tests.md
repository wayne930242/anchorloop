# Minimize tests

**When:** Before any verify or gate run, and whenever a fix, merge, or rebase changes a tree that already has a green run.

This principle takes priority over a skill or project rule that would repeat a green run whose inputs did not change (the user's standing rule, 2026-11-11). Passed runs on record are required context: collect those for this tree or an ancestor (command with filter, SHA, result), whether your own, a worker's, CI's, or another gate's. Run only what covers `git diff <last green sha>..HEAD`; reuse a run whose inputs did not change. A whole suite runs only where a gate requires it, once per tree. Record each run (command with filter, SHA, result) where the next round reads it: the MR description, todo metadata, or the report.

A run made for another purpose is not a repeat: the red-first run of a new or changed check, the one flake rerun, reproducing a finding, and a measurement's repeated runs all still happen.

The last green SHA is per command and filter: a filtered run is green only for what it ran. Covering the diff means the tests of the changed files, of their callers and consumers, and every tree-wide check whose inputs include a changed file (the coding Anchor). An uncommitted or untracked change, or a changed lockfile, toolchain, environment, or fixture, is a changed input. When the covering set cannot be determined, run the gate's suite.

A reused run is reported as its own claim with its source, command, and SHA, never as a different kind of claim (local, CI, deploy); CI state is re-queried, a record without a SHA or command is not reused, and reuse needs the same command in the same environment or target. With no green run on record, the anchor runs as stated; narrowing an anchor's command is reported together with the reused run that covers the rest.
