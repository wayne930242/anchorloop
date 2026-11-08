# Rollback

**You own getting each target back to a known version, and the car that caused it back to its author.**

1. **Read.** Read the failing target's state and the run's conclusion; a rollout that reports healthy can still be a failed deploy when `Deploy verify` shows another version.
2. **Roll back as `Deploy` says,** or retry where `Deploy` lists the failure as retryable. Apply Rules 1, 3, and 4 of [Rules](../SKILL.md#rules) (exclusions, dry run, target check); the version rolled back to was tested when it shipped, so Rule 2 does not delay it.
3. **Verify the rollback.** The target runs the previous version, read as `Deploy verify` reads it; the rollback is done only then.
4. **Return the car.** A failed target sends its car back as a red one: car, failing target, log path, and the `train` SHA ([train](../../integrating/playbooks/train.md) step 5).
5. **Revert after landing.** A revert on the integration branch (a car's merge commit reverted after the push, or an acceptance finding on the coordinator's side) goes as its own train through review, `Full gates`, `Merge`, and `Deploy`, because the targets must stop running the reverted car.
6. **Record** the version each target runs now, the returned or held cars, and the revert train's `<code>` in the ledger.

**Reply:** the failing target and its evidence, the version each target runs now (observed), the cars returned or held, and the revert train when one was needed.
