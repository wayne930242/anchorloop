# MultiTask

TLC reached 58 states and 99 steps. The chart draws 11 states and 9 arrows.
The chart does not draw 33 steps that stay in one chart state.
The step you close the loop changes MP-1001 and MP-1002 at the same time.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1002: its worker edits in its worktree: MP-1001 not started, MP-1002 worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001 not started, MP-1002 checked, book asks for the check

## QuietWhileWaiting breaks
The shortest path has 5 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1002: its worker edits in its worktree: MP-1001 not started, MP-1002 worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001 not started, MP-1002 checked, book asks for the check
4. MP-1001: you start its worker: MP-1001 worker started, MP-1002 checked, book asks for the check
5. your turn ends: the notice asks MP-1002 for verify: MP-1001 worker started, MP-1002 checked, book asks for the check

## Rules that hold
TypeOK, NotLent, Isolation, OnePerChange, AskOnlyOwed, OwedIsNamed, CanClose, AcceptedCounts
