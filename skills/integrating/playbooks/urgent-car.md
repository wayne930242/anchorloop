# Urgent car

**You own the exception.** An urgent car still gets review and gates; the lane only changes its place in the queue.

1. **Qualify.** `urgent` is only the approver's explicit "first", a fix of a P0 defect in a live deploy target, or a fix-forward car. The slip's `lane` line names the ground; any other ground returns the car to the normal lane.
2. **Place it.** The car departs per the project skill's `Urgent lane`. Without that heading it waits for a running gate to finish, because an interrupted gate leaves a half-tested head.
3. **Fix-forward car.** `lane: urgent (fix-forward: <red pipeline>)` holds only the fix of a red integration branch. Its `review` may be the author's read with no report path. It departs at once and alone, whether the branch is red or not. The train's reviewer gives it its first full-depth review, reading the car's whole diff and not a delta, and `Full gates` still run before `Merge`.
4. **Everything else follows [train](train.md)** from step 2. A car without a report path that is not a fix-forward car is returned ([receive-car](receive-car.md)).

**Reply:** the ground for urgency, where the car departed, and its review and gate evidence.
