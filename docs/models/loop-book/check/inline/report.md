# LoopBook

TLC reached 84 states and 316 steps. The chart draws 12 states and 42 arrows.
The chart does not draw 128 steps that stay in one chart state.

## CanFinish breaks
The shortest path has 3 steps:
0. No change yet
1. you list an observation to make after landing: No change yet; no ref watched
2. you change the code: Changed, check missing; no ref watched
3. you run the anchor: it passes: Check passed, observation waits for a landing; no ref watched

## Rules that hold
TypeOK, KeptDone, AcceptedCounts, ReportedReviewCounts, QuietWhileWaiting, NoStalePass, ReviewReadTheChange, CloseNeedsOnlyTodos
