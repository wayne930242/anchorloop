# LoopBook

TLC reached 102 states and 416 steps. The chart draws 14 states and 58 arrows.
The chart does not draw 124 steps that stay in one chart state.

## CanFinish breaks
The shortest path has 2 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you run the anchor: it passes: Checked, review missing

## ReportedReviewCounts breaks
The shortest path has 3 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a reviewer and wait: Changed, check missing; reviewer reading
3. the review comes back: Blocking P0=0 P1=0, and the book records no review: Changed, check missing; a review came back with no blocking finding

## Rules that hold
TypeOK, KeptDone, AcceptedCounts, QuietWhileWaiting, NoStalePass, ReviewReadTheChange, CloseNeedsOnlyTodos
