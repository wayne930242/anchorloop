# LoopBook

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 4 states and 4 arrows.

## ReviewReadTheChange breaks
The shortest path has 4 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a reviewer and wait: Changed, check missing; reviewer reading
3. you change the code: Changed, check missing; reviewer reading
4. the review comes back: Blocking P0=0 P1=0: Changed, check missing; the code changed while the reviewer read

## Rules not checked
TypeOK
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked this rule in every state.
