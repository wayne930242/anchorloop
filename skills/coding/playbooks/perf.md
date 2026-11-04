# Perf

**You own the number.** The [benchmark checklist](../references/benchmark-checklist.md) holds the measurement checks; run it before any number is reported.

1. Anchor: before measuring, write the claim you expect to ship, the result that would change the decision, and the noise floor (**Explain the number**); stop when the run-to-run spread exceeds the effect. Read what the script times and counts. Measure a baseline on the real workload, at least 5 runs per side alternating, as a median and range, after checking `uptime`. The harness prints its error count and the work it finished, and the behavior tests run green first. When the base lacks the feature, measure the work the diff adds and the end state, never a ratio between unlike scenarios. For an iterated run, prove the harness separates a known-slow case from a known-fast one, then freeze it.
2. Act: **Explain the number**: name the limiter from a profile or counters, and rule out a warm cache, a skipped path, a debug build, an untuned side, and a piece too small to matter end to end. Profile before changing code.
3. Act: one change at a time against the baseline, trying the cheapest idea first: do not do the work, do not redo it, do less of it, do it later, do it concurrently, do it more cheaply. Keep a change only when its gain sits outside the noise and the behavior tests stay green, and revert the rest.
4. Verify: rerun the baseline workload under the same conditions, alternating base and change runs.

**Reply:** faster, slower, no measurable difference, or inconclusive (a claimed difference with no named limiter, an untuned side, or unchecked errors and work), with run counts, ranges, the delta, what limits the number, the profile that pointed at the change, the harness path, and the best idea left untried.
