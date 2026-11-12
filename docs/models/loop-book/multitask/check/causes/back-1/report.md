# MultiTask

TLC reached 1,780 states, more than the chart budget of 500, so the chart draws only the bug paths: 15 states and 15 arrows.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
2. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: not started | MP-1002: checked, book asks for the check

## Isolation breaks
The shortest path has 7 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker edits in its worktree: MP-1001: worker editing | MP-1002: not started
3. MP-1001's worker returns, its check passed: MP-1001: checked, review missing | MP-1002: not started
4. MP-1002: you start its worker: MP-1001: checked, review missing | MP-1002: worker started
5. MP-1002: its worker edits in its worktree: MP-1001: checked, review missing | MP-1002: worker editing
6. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: checked, review missing | MP-1002: checked, book asks for the check
7. MP-1002: sb returns its car: you declare back for it: MP-1001: checked, book asks for the check | MP-1002: car returned, rework

## NotLent breaks
The shortest path has 11 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker edits in its worktree: MP-1001: worker editing | MP-1002: not started
3. MP-1001's worker returns, its check passed: MP-1001: checked, review missing | MP-1002: not started
4. MP-1002: you start its worker: MP-1001: checked, review missing | MP-1002: worker started
5. MP-1002: its worker edits in its worktree: MP-1001: checked, review missing | MP-1002: worker editing
6. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: checked, review missing | MP-1002: checked, book asks for the check
7. MP-1001: you send it to the persistent reviewer: MP-1001: reviewer reading | MP-1002: checked, book asks for the check
8. the reviewer comes back clear for MP-1001: MP-1001: complete | MP-1002: checked, book asks for the check
9. MP-1001: sb returns its car: you declare back for it: MP-1001: car returned, rework | MP-1002: checked, book asks for the check
10. MP-1002: you send it to the persistent reviewer: MP-1001: car returned, rework | MP-1002: reviewer reading
11. the reviewer comes back clear for MP-1002: MP-1001: car returned, rework | MP-1002: checked, book asks for the check

## Rules that hold
TypeOK, OnePerChange, AskOnlyOwed, QuietWhileWaiting, OwedIsNamed, CanClose, AcceptedCounts
