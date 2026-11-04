# Benchmark checklist

Run it before reporting a performance number. Each item names the way a number comes out wrong.

1. **Claim.** Write the sentence you expect to ship, the result that would change the decision, and the noise floor, before the first run. A claim shaped after the numbers arrive fits whatever they say.
2. **Script.** Read what the measurement script times, counts, and ignores. A timer that covers setup, or the wrong function, measures something else.
3. **Same footing.** Run every compared side the way production runs it: release build, flags, pools, and caches as warm or cold as production, with the same data and versions. A side on defaults means you compared configurations, so no winner follows from that run. When the base lacks the feature, measure the work the diff adds and the end state; a ratio between unlike scenarios compares nothing.
4. **Work done.** The harness prints its error count and the units of work it finished. Fast failures and lazy code (a generator nobody iterates, a promise nobody awaits) look like speed. Confirm the work ran inside the timed region.
5. **Quiet machine.** Read `uptime` and the core count first; stop competing work, or interleave the sides when you cannot. Orphan processes and a busy box turn drift into a "gain".
6. **Counts.** At least 5 runs per side, alternating (A, B, A, B), reporting the median and range. A gap inside the run-to-run range is "no measurable difference". The base and the change alternate too, so thermal and cache drift hit both.
7. **Limits.** Removing a piece that takes 10% of the run speeds it up by at most about 11%. Report a micro result as a share of the end-to-end path. A number past a hardware limit (disk, core count, network) measured something other than the work.
8. **Limiter.** Ask why not double. Name the limiter from a profile or system counters; a guess from reading the code is not one. Profile in a run you do not report, because profilers slow the work, and when the load generator saturates first, you measured the load generator.
9. **Behavior.** The behavior tests run green before the baseline and after each change. A faster run that fails them, or that returns different output, is reverted.

The verdict is `inconclusive` when you claim a difference but cannot name the limiter, a side ran untuned, or you could not check items 4 and 7.

A quick ballpark the user asked for needs one run. Still check items 4 and 7 and say it is one run; a choice between options is never a ballpark.

---

Adapted from pstack `benchmark-checklist` by Lauren Tan (MIT License), revision `c742dd6` of cursor/plugins.
