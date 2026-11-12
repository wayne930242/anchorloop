# MultiTask

TLC reached 905 states, more than the chart budget of 500, so the chart draws only the bug paths: 6 states and 5 arrows.

## OwedIsNamed breaks
The shortest path has 5 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker edits in its worktree: MP-1001: worker editing | MP-1002: not started
3. MP-1001's worker returns, its check passed: MP-1001: checked, review missing | MP-1002: not started
4. MP-1002: you start its worker: MP-1001: checked, review missing | MP-1002: worker started
5. your turn ends: no notice: MP-1001: checked, review missing | MP-1002: worker started; turn over

## Rules that hold
TypeOK, Counted, NotLent, Isolation, OnePerChange, AskOnlyOwed, QuietWhileWaiting, CanClose, AcceptedCounts
