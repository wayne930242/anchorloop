# Receive a car

**You own the slip.** A car enters a train only with a complete slip whose every claim you checked; the author's side builds the slip, the owner's side checks it. A session that is both does both, and checks as strictly as for a stranger's car.

1. **Build the slip (author).** Send one complete block through the handoff route:

       car: <app> | tickets: <ids> | branch: <name> | head: <sha40> | tested-on: <base sha>
       review: P0=0 P1=0 (<report path>)|author's read (fix-forward)|author's read (test-only) | light: pass (<commands and result per Light checks>)
       migrations: <names or none> (applied to a DB: no|<which>) | lane: normal|urgent (<ground for urgent>)
       deploy: <targets or none> | departs: <next|alone|with <ticket or branch>|after <ISO time>|by <ISO time>, comma-separated>
       accept: <evidence file or none>
       auth: "<the approver's words>" | coordinator: <who answers for the car>

   `departs` defaults to `next`. `accept` names a file listing the accepted head, quoted nod, and result per required kind, or `none` when Settings' `accept` is empty. Obtain `auth` through the approval seam for the integration branch and every `strict` deploy target.

   In either lane, the coordinator reads the whole diff against these conditions and can send `review: author's read (test-only)` in place of a separate car review. The diff stays on test paths: files that only test targets build or load, including specs, test project files and their own manifests, fixtures, and test data. Use any test path patterns named by the project skill and confirm target membership. Production source (including test helpers compiled into production), generated files, migrations, CI config, and shared build config or dependency manifests take the regular review path.
   Keep every test, case, and assertion active and gating in the same runs, with the same scope and strength. Keep limits, tolerances, timeouts, floors, baselines, benchmarks, and ratchets at least as strict. Derive expected values from the spec or an independent computation; snapshots or goldens regenerated from current output take the regular review path. Record the fixed tests' red-before and green-after runs in `light`; a recorded failing CI run of the same test before the fix counts for a time-dependent failure.

2. **Check it (owner).** Each of these holds, else return the car to its coordinator with the failed check:
   - `head` is still the branch tip.
   - `auth` covers the integration branch and every `strict` target in `deploy`.
   - `review` has a report path, reads `author's read (fix-forward)` and qualifies under [urgent-car](urgent-car.md), or reads `author's read (test-only)` and the car diff names only eligible test paths (check both sides of renames).
   - Every kind in Settings' `accept` has evidence in the `accept` file: its accepted head equals `head` (or is an ancestor with a delta the project skill's `Acceptance` allows), the nod is quoted, and the result is passed. A slip that asks the train to run or wait for acceptance is returned with that named.
   - No migration is applied to a DB, because train assembly cannot regenerate an applied one.
3. **Group cars** by the targets their `auth` covers, so the train never asks later. Record the car in the ledger and answer its coordinator with the train number and departure conditions ([train](train.md) step 1).

**Reply:** each car received or returned, the failed check for a returned one, and the train it joined.
