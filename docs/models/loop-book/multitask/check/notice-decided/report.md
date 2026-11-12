# MultiTask

TLC reached 22,356 states, more than the chart budget of 500, so the chart draws only the bug paths: 8 states and 9 arrows.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
2. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: not started | MP-1002: checked, book asks for the check

## OwedIsNamed breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker dies (model quota): MP-1001: worker died | MP-1002: not started
3. your turn ends: no notice: MP-1001: worker died | MP-1002: not started; turn over

## OnePerChange breaks
The shortest path has 4 steps:
0. MP-1001: not started | MP-1002: not started
1. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: not started; turn over
2. you /reload after an install: MP-1001: not started | MP-1002: not started; turn over
3. someone else starts your turn: MP-1001: not started | MP-1002: not started
4. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: not started; turn over

## Rules that hold
TypeOK, NotLent, Isolation, AskOnlyOwed, QuietWhileWaiting, CanClose, AcceptedCounts
