# LoopBook

TLC reached 258 states and 1142 steps. The chart draws 27 states and 146 arrows.
The chart does not draw 223 steps that stay in one chart state.

## AcceptedCounts breaks
The shortest path has 1 step:
0. No change yet
1. you declare a passing verify with no task: the tool answers ok: No change yet; the tool answered ok to a verify

## ReviewReadTheChange breaks
The shortest path has 4 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a reviewer and wait: Changed, check missing; reviewer reading
3. you change the code: Changed, check missing; reviewer reading
4. the review comes back: Blocking P0=0 P1=0: Changed, check missing; the code changed while the reviewer read

## Rules that hold
TypeOK, KeptDone, ReportedReviewCounts, CanFinish, QuietWhileWaiting, NoStalePass, CloseNeedsOnlyTodos
