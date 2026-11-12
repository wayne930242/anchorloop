# LoopBook

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 7 states and 6 arrows.

## QuietWhileWaiting breaks
The shortest path has 6 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a worker and wait: Changed, check missing; worker out
3. you start a reviewer and wait: Changed, check missing; worker out; reviewer reading
4. your turn ends: no notice: Changed, check missing; worker out; reviewer reading; turn over
5. the worker returns: Changed, check missing; reviewer reading
6. your turn ends: the notice judges the loop: Changed, check missing; reviewer reading; judged while waiting; turn over

## Rules not checked
TypeOK
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked this rule in every state.
