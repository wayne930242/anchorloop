# Perf

**You own the number.** The [benchmark checklist](../references/benchmark-checklist.md) holds the measurement checks; run it before any number is reported.

1. Anchor: apply [**Explain the number**](../../anchorloop/principles/explain-the-number.md), then measure a baseline on the real workload under checklist items 1 to 6 and 9. For an iterated run, prove the harness separates a known-slow case from a known-fast one, then freeze it.
2. Act: name the limiter and rule out a false number (checklist items 3, 4, 7, and 8). Profile before changing code.
3. Act: one change at a time against the baseline, trying the cheapest idea first: do not do the work, do not redo it, do less of it, do it later, do it concurrently, do it more cheaply. Keep a change only when its gain sits outside the noise and the behavior tests stay green, and revert the rest.
4. Verify: rerun the baseline workload under the same conditions, alternating base and change runs.

**Reply:** faster, slower, no measurable difference, or inconclusive (as the checklist defines it), with run counts, ranges, the delta, what limits the number, the profile that pointed at the change, the harness path, and the best idea left untried.
