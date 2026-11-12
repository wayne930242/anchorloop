# MultiTask

TLC reached 10,704 states, more than the chart budget of 500, so the chart draws only the bug paths: 12 states and 13 arrows.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1002: you start its worker: MP-1001: not started | MP-1002: worker started
2. MP-1002: its worker edits in its worktree: MP-1001: not started | MP-1002: worker editing
3. MP-1002's worker returns, its check passed: the book does not count it: MP-1001: not started | MP-1002: checked, book asks for the check

## Isolation breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, review missing | MP-1002: not started
3. MP-1002: you change its code yourself: MP-1001: checked, book asks for the check | MP-1002: changed, check missing

## NotLent breaks
The shortest path has 9 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, review missing | MP-1002: not started
3. MP-1001: you send it to the persistent reviewer: MP-1001: reviewer reading | MP-1002: not started
4. MP-1002: you change its code yourself: MP-1001: reviewer reading | MP-1002: changed, check missing
5. MP-1002: you run its anchor: it passes: MP-1001: reviewer reading | MP-1002: checked, review missing
6. the reviewer comes back clear for MP-1001: MP-1001: checked, book asks for the check | MP-1002: checked, review missing
7. MP-1001: sb returns its car: you declare back for it: MP-1001: not started | MP-1002: checked, book asks for the check
8. MP-1002: you send it to the persistent reviewer: MP-1001: not started | MP-1002: reviewer reading
9. the reviewer comes back clear for MP-1002: MP-1001: not started | MP-1002: checked, book asks for the check

## Rules that hold
TypeOK, OnePerChange, AskOnlyOwed, QuietWhileWaiting, OwedIsNamed, CanClose, AcceptedCounts
