# MultiTask

TLC reached 9,483 states, more than the chart budget of 500, so the chart draws only the bug paths: 11 states and 13 arrows.

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
The shortest path has 9 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
2. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
3. your turn ends: no notice: MP-1001: not started | MP-1002: worker editing; turn over
4. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: not started | MP-1002: checked, book asks for the check
5. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: checked, book asks for the check; turn over
6. a todo is added or completed: MP-1001: not started | MP-1002: checked, book asks for the check; turn over
7. someone else starts your turn: MP-1001: not started | MP-1002: checked, book asks for the check
8. MP-1002: you run its anchor: it passes: MP-1001: not started | MP-1002: checked, review missing
9. your turn ends: the notice asks MP-1001 for act: MP-1001: not started | MP-1002: checked, review missing; turn over

## Rules that hold
TypeOK, NotLent, Isolation, AskOnlyOwed, QuietWhileWaiting, CanClose, AcceptedCounts
