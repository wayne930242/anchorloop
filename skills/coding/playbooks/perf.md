# Perf

**You own the number.** Run the [benchmark checklist](../references/benchmark-checklist.md) before any number is reported.

1. Anchor: predict the number and what would change the decision, then measure a baseline on the real workload under checklist items 1 to 6 and 9. For an iterated run, prove the harness separates a known-slow case from a known-fast one, then freeze it.
2. Name the limiter and rule out a false number (items 3, 4, 7, and 8). Profile before changing code.
3. One change at a time against the baseline, cheapest idea first: skip the work, do not redo it, do less, do it later, do it concurrently, do it more cheaply. Keep a change only when its gain sits outside the noise and the behavior tests stay green.
4. Verify: rerun the baseline workload under the same conditions, alternating base and change runs.

**Reply:** faster, slower, no measurable difference, or inconclusive (as the checklist defines it), with run counts, ranges, the delta, the limiter, the harness path, and the best idea left untried.
