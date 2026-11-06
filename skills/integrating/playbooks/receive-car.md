# Receive a car

**You own the slip.** A car enters a train only with a complete slip whose every claim you checked; the author's side builds the slip, the owner's side checks it. A session that is both does both, and checks as strictly as for a stranger's car.

1. **Build the slip (author).** One block, one missing field returns it:

       car: <app> | tickets: <ids> | branch: <name> | head: <sha40> | tested-on: <base sha>
       review: P0=0 P1=0 (<report path>)|author's read (fix-forward) | light: pass (<commands and result per Light checks>)
       migrations: <names or none> (applied to a DB: no|<which>) | lane: normal|urgent (<ground for urgent>)
       deploy: <targets or none> | uat: <checkpoints path or none>
       auth: "<the approver's words>" | coordinator: <who answers for the car>

   Send it through the handoff route. `auth` is a quote of the approver's own words that cover the integration branch and every `strict` target in `deploy`; obtain it through the approval seam, never by writing it yourself.
2. **Check it (owner).** Each of these holds, else return the car to its coordinator with the failed check:
   - `head` is still the branch tip.
   - `auth` covers the integration branch and every `strict` target in `deploy`.
   - `review` has a report path; the one exception is `author's read` on a fix-forward car, which [urgent-car](urgent-car.md) checks further.
   - A `uat` file lists, per checkpoint, its flow, state, steps, and expected result, and the slip names a target for it (`deploy` or an `auto` one).
   - No migration is applied to a DB, because train assembly cannot regenerate an applied one.
3. **Answer the coordinator** with the train number and the departure conditions ([train](train.md) step 1), and record the car in the ledger.

**Reply:** each car received or returned, the failed check for a returned one, and the train it joined.
