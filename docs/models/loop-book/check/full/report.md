# LoopBook

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 13 states and 15 arrows.

## KeptDone breaks
The shortest path has 2 steps:
0. No change yet
1. you run the anchor: it passes: No change yet
2. you write a file in another repository: Changed, check missing; a check passed and nothing it tests changed since

## NoStalePass breaks
The shortest path has 2 steps:
0. No change yet
1. you run the anchor: it passes: No change yet
2. you change the code through a shell command: No change yet; the code changed after the check

## ReportedReviewCounts breaks
The shortest path has 3 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you ask a subagent of another role to review, and wait: Changed, check missing; another role reviewing
3. the review comes back: Blocking P0=0 P1=0, and the book records no review: Changed, check missing; a review came back with no blocking finding

## CanFinish breaks
The shortest path has 3 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you run the anchor: it passes: Checked, review missing
3. you list an observation to make after landing: Check passed, observation waits for a landing; no ref watched

## ReviewReadTheChange breaks
The shortest path has 4 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a reviewer and wait: Changed, check missing; reviewer reading
3. you change the code: Changed, check missing; reviewer reading
4. the review comes back: Blocking P0=0 P1=0: Changed, check missing; the code changed while the reviewer read

## QuietWhileWaiting breaks
The shortest path has 5 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a worker and wait: Changed, check missing; worker out
3. your turn ends: no notice: Changed, check missing; worker out; turn over
4. someone speaks to you: Changed, check missing; worker out
5. your turn ends: the notice judges the loop: Changed, check missing; worker out; judged while waiting; turn over

## Rules not checked
TypeOK, AcceptedCounts, CloseNeedsOnlyTodos
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked these rules in every state.
