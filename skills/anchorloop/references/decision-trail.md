# Decision trail

Read when a run the user reviews after stepping away starts, continues, or hands back a trail, whether or not it is an autonomous run.

Record one row per fork, pivot, or blocker in `scratch/decisions-<task-slug>.tsv` with the `anchorloop_decision` tool (git log holds the iterations). A discarded attempt gets a row too (approach, the predicate or check reading, why dropped), because it never reaches git log and the next run would retry it. Evidence is a pointer (commit, `file:line`, artifact path), never prose, and a wrong call gets a superseding row instead of an edit. A run that continues a trail first records a `start` row with its run id.

Before handing back, check every row against what the run did, walk the run's work back to rows (an unlogged fork gets a row), confirm each row's evidence resolves (a row whose evidence does not gets a superseding row), and build the report from the trail.
