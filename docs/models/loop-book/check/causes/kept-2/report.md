# LoopBook

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 3 states and 3 arrows.

## KeptDone breaks
The shortest path has 3 steps:
0. No change yet
1. you run the anchor: it passes: No change yet
2. you start a worker and wait: No change yet; worker out
3. the worker edits in its own worktree: Changed, check missing; a check passed and nothing it tests changed since; worker out

## Rules not checked
TypeOK
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked this rule in every state.
