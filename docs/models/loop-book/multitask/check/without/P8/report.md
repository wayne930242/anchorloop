# MultiTask

TLC reached 934 states, more than the chart budget of 500, so the chart draws only the bug paths: 4 states and 3 arrows.

## Counted breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, car not landed | MP-1002: not started
3. MP-1001: sb's notice: its car landed; you declare it: MP-1001: landed, book sees no landing | MP-1002: not started

## CanClose breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, car not landed | MP-1002: not started
3. MP-1001: sb's notice: its car landed; you declare it: MP-1001: landed, book sees no landing | MP-1002: not started

## Rules that hold
TypeOK, NotLent, Isolation, OnePerChange, AskOnlyOwed, QuietWhileWaiting, OwedIsNamed, AcceptedCounts
