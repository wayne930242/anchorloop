# MultiTask

TLC reached 1,926 states, more than the chart budget of 500, so the chart draws only the bug paths: 6 states and 7 arrows.

## OwedIsNamed breaks
The shortest path has 4 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
2. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
3. MP-1002's worker returns, its check passed: MP-1001: not started | MP-1002: checked, review missing
4. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: checked, review missing; turn over

## OnePerChange breaks
The shortest path has 7 steps:
0. MP-1001: not started | MP-1002: not started
1. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: not started; turn over
2. a todo is added or completed: MP-1001: not started | MP-1002: not started; turn over
3. someone else starts your turn: MP-1001: not started | MP-1002: not started
4. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
5. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
6. MP-1002's worker returns, its check passed: MP-1001: not started | MP-1002: checked, review missing
7. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: checked, review missing; turn over

## Rules that hold
TypeOK, Counted, NotLent, Isolation, AskOnlyOwed, QuietWhileWaiting, CanClose, AcceptedCounts
