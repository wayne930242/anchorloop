# MultiTask

TLC reached 7,876 states, more than the chart budget of 500, so the chart draws only the bug paths: 6 states and 5 arrows.

## Counted breaks
The shortest path has 5 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, review missing | MP-1002: not started
3. MP-1001: you send it to the persistent reviewer: MP-1001: reviewer reading | MP-1002: not started
4. the reviewer comes back clear for MP-1001: MP-1001: complete | MP-1002: not started
5. MP-1002: you change its code yourself: MP-1001: reviewed clear, book asks for a review | MP-1002: changed, check missing

## Isolation breaks
The shortest path has 5 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, review missing | MP-1002: not started
3. MP-1001: you send it to the persistent reviewer: MP-1001: reviewer reading | MP-1002: not started
4. the reviewer comes back clear for MP-1001: MP-1001: complete | MP-1002: not started
5. MP-1002: you change its code yourself: MP-1001: reviewed clear, book asks for a review | MP-1002: changed, check missing

## Rules that hold
TypeOK, NotLent, OnePerChange, AskOnlyOwed, QuietWhileWaiting, OwedIsNamed, CanClose, AcceptedCounts
