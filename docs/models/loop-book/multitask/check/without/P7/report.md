# MultiTask

TLC reached 2,546 states, more than the chart budget of 500, so the chart draws only the bug paths: 4 states and 5 arrows.

## CanClose breaks
The shortest path has 2 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you hand off to a new session: MP-1001: work done, book shows no change | MP-1002: not started; new session

## Counted breaks
The shortest path has 3 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, car not landed | MP-1002: not started
3. MP-1001: you hand off to a new session: MP-1001: work done, book shows no change | MP-1002: not started; new session

## AcceptedCounts breaks
The shortest path has 4 steps:
0. MP-1001: not started | MP-1002: not started
1. MP-1001: you change its code yourself: MP-1001: changed, check missing | MP-1002: not started
2. MP-1001: you run its anchor: it passes: MP-1001: checked, car not landed | MP-1002: not started
3. MP-1001: you hand off to a new session: MP-1001: work done, book shows no change | MP-1002: not started; new session
4. MP-1001: you declare its verify with its task: MP-1001: work done, book shows no change | MP-1002: not started; new session

## Rules that hold
TypeOK, NotLent, Isolation, OnePerChange, AskOnlyOwed, QuietWhileWaiting, OwedIsNamed
