# Minimize tests

**When:** Before any verify or gate run, and whenever a fix, merge, or rebase changes a tree that already has a green run.

Passed runs on record are required context: collect those for this tree or an ancestor (command with filter, SHA, result), whether your own, a worker's, CI's, or another gate's. Run only what covers `git diff <last green sha>..HEAD`; reuse a run whose inputs did not change. A whole suite runs only where a gate requires it, once per tree. Record each run (command with filter, SHA, result) where the next round reads it: the MR description, todo metadata, or the report.
