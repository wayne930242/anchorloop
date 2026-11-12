# LoopBook

TLC reached 162 states and 668 steps. The chart draws 7 states and 21 arrows.
The chart does not draw 261 steps that stay in one chart state.
The view hides 100 steps, so the chart does not draw them.
With VIEW, TLC keeps one representative for each group of states that it counts as the same. An arrow can lead to the representative rather than to the state that the step reaches.

## ReviewReadTheChange breaks
The shortest path has 4 steps:
0. No change yet
1. you change the code: Changed, check missing
2. you start a reviewer and wait: Changed, check missing
3. you change the code: Changed, check missing
4. the reviewer you started comes back: Blocking P0=0 P1=0: Changed, check missing

## Rules that hold
TypeOK, KeptDone, AcceptedCounts, ReportedReviewCounts, CanFinish, QuietWhileWaiting, NoStalePass, CloseNeedsOnlyTodos
