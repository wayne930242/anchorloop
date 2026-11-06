# Deploy

**You own each target's deploy and its proof.** A target is done when it runs the shipped version; the job that ran is not the proof.

1. **List the targets and their order.** The targets are every `auto` target of the settings plus each target the slips name, in the order `Deploy` gives; outside a train, the targets the user names.
2. **Check approval per target.** An `auto` target needs no per-car words. A `strict` target takes the train only when every car in it has `auth` naming it, since a deploy ships every car. Otherwise skip that target for now and ask the approver whether to deploy it or hold the cars it does not cover. A held car is not landed; held before `Merge`, it leaves the train as a dropped car does. Where merging deploys a `strict` target, ask before `Merge`.
3. **Serialize per target.** One train at a time per target: a later train waits for the earlier one's `Deploy verify` there, and where merging deploys a target (`Deploy` says), the next train's `Merge` waits for it too. An older pipeline that queued longer once deployed after a newer one and rolled a target back.
4. **Announce** a deploy you start yourself through the escalation route, naming the target; a deploy your merge triggers needs none.
5. **Prepare each target.** Do what `Deploy` adds for it (a confirmation, a window, a backup), apply the [Rules](../SKILL.md#rules), and on production or any live target run the dry run first and read what it plans.
6. **Deploy,** in order, per `Deploy`.
7. **Verify** each target with `Deploy verify`: done is the target running this train's own version, read from the target. A green job, an accepted request, or a finished monitor is not done; read the run's conclusion, not that its monitor ended.
8. **Failure** on a target goes to [rollback](rollback.md).
9. **Record** the version each target runs in the ledger, and the verdict per target.

**Reply:** per target, the approval (quoted or `auto`), the dry run's planned changes, the version observed after the deploy, and any target held, failed, or rolled back.
