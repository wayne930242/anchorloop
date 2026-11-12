# MultiTask

TLC reached 98 states and 128 steps. The chart draws 11 states and 9 arrows.
The chart does not draw 43 steps that stay in one chart state.
The step you close the loop changes MP-1001 and MP-1002 at the same time.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1002: its worker edits in its worktree: MP-1001 not started, MP-1002 worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001 not started, MP-1002 checked, book asks for the check

## OwedIsNamed breaks
The shortest path has 4 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1002: its worker edits in its worktree: MP-1001 not started, MP-1002 worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001 not started, MP-1002 checked, book asks for the check
4. your turn ends: no notice: MP-1001 not started, MP-1002 checked, book asks for the check

## AskOnlyOwed breaks
The shortest path has 6 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1001: you start its worker: MP-1001 worker started, MP-1002 worker started
3. MP-1001: its worker edits in its worktree: MP-1001 worker editing, MP-1002 worker started
4. your turn ends: no notice: MP-1001 worker editing, MP-1002 worker started
5. MP-1001's worker returns, its check passed: MP-1001 complete, MP-1002 worker started
6. your turn ends: the notice asks MP-1002 for act: MP-1001 complete, MP-1002 worker started

## QuietWhileWaiting breaks
The shortest path has 6 steps:
0. MP-1001 not started, MP-1002 not started
1. MP-1002: you start its worker: MP-1001 not started, MP-1002 worker started
2. MP-1001: you start its worker: MP-1001 worker started, MP-1002 worker started
3. MP-1001: its worker edits in its worktree: MP-1001 worker editing, MP-1002 worker started
4. your turn ends: no notice: MP-1001 worker editing, MP-1002 worker started
5. MP-1001's worker returns, its check passed: MP-1001 complete, MP-1002 worker started
6. your turn ends: the notice asks MP-1002 for act: MP-1001 complete, MP-1002 worker started

## Rules that hold
TypeOK, NotLent, Isolation, OnePerChange, CanClose, AcceptedCounts
