# MultiTask

TLC reached 53,200 states, more than the chart budget of 500, so the chart draws only the bug paths: 6 states and 7 arrows.

## QuietWhileWaiting breaks
The shortest path has 4 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker dies (model quota): MP-1001: worker died | MP-1002: not started
3. MP-1002: you start its worker: MP-1001: worker died | MP-1002: worker started
4. your turn ends: the notice asks MP-1001 for act: MP-1001: worker died | MP-1002: worker started; turn over

## OnePerChange breaks
The shortest path has 6 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you start its worker: MP-1001: worker started | MP-1002: not started
2. MP-1001: its worker dies (model quota): MP-1001: worker died | MP-1002: not started
3. your turn ends: the notice asks MP-1001 for act: MP-1001: worker died | MP-1002: not started; turn over
4. you /reload after an install: MP-1001: worker died | MP-1002: not started; turn over
5. someone else starts your turn: MP-1001: worker died | MP-1002: not started
6. your turn ends: the notice asks MP-1001 for act: MP-1001: worker died | MP-1002: not started; turn over

## Rules that hold
TypeOK, Counted, NotLent, Isolation, AskOnlyOwed, OwedIsNamed, CanClose, AcceptedCounts
