# LoopBook

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 2 states and 2 arrows.

## KeptDone breaks
The shortest path has 2 steps:
0. No change yet
1. you run the anchor: it passes: No change yet
2. you write a note git ignores: Changed, check missing; a check passed and nothing it tests changed since

## Rules not checked
TypeOK
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked this rule in every state.
