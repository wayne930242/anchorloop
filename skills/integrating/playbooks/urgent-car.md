# Urgent car

**You own the exception.** An urgent car still gets review and gates; the lane only changes its place in the queue.

1. **Qualify.** Use `urgent` for the approver's explicit "first", a P0 fix in a live deploy target, or a fix-forward car. Name the ground in `lane`; other cars use `normal`.
2. **Place it.** It goes ahead of every normal car and departs without waiting for `maxCars` or `maxWaitMin`; [train](train.md) step 1's `Load` and red-pipeline conditions still hold (a fix-forward car: step 3). `Urgent lane`, when present, says more; a running gate is interrupted only if it says so, because an interrupted gate leaves a half-tested head.
3. **Fix-forward car.** `lane: urgent (fix-forward: <red pipeline>)` holds only the fix of the integration branch's red pipeline. Check that the named pipeline is the branch's latest and is red; else return the car. Its `review` may read `author's read (fix-forward)`. It departs as the next train, alone, whether the branch is red or not, once `Load` allows. The train's reviewer gives it its first full-depth review: the whole diff, not a delta, and whether the car holds only that fix; a car holding more is returned. Each new SHA of the car gets the full review until one passes, and `Full gates` still run before `Merge`.
4. **Follow [train](train.md)** from step 2 for other urgent cars accepted by [receive-car](receive-car.md).

**Reply:** the ground for urgency, where the car departed, and its review and gate evidence.
