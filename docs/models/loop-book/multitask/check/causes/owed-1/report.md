# MultiTask

TLC reached 2,338 states, more than the chart budget of 500, so the chart draws only the bug paths: 11 states and 12 arrows.

## OwedIsNamed breaks
The shortest path has 4 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker edits in its worktree: MP-1001: worker editing | MP-1002: not started
3. MP-1001's worker returns, its check passed: MP-1001: checked, review missing | MP-1002: not started
4. your turn ends: no notice: MP-1001: checked, review missing | MP-1002: not started; turn over

## OnePerChange breaks
The shortest path has 8 steps:
0. MP-1001: not started | MP-1002: not started
1. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: not started; turn over
2. a todo is added or completed: MP-1001: not started | MP-1002: not started; turn over
3. someone else starts your turn: MP-1001: not started | MP-1002: not started
4. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
5. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
6. your turn ends: no notice: MP-1001: not started | MP-1002: worker editing; turn over
7. MP-1002's worker returns, its check passed: MP-1001: not started | MP-1002: checked, review missing
8. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: checked, review missing; turn over

## Rules that hold
TypeOK, Counted, NotLent, Isolation, AskOnlyOwed, QuietWhileWaiting, CanClose, AcceptedCounts
