# Bug fix

**You own the root cause.** Every shipped line traces to runtime evidence.

1. Anchor: build one tight, agent-runnable loop that asserts the user's exact symptom (failing test, request script, CLI fixture, browser check, replay, bisection, or differential comparison) and watch it go red for the symptom's reason. For flaky behavior, raise and measure the reproduction rate, then minimize until every element is load-bearing. When no red loop can be built, tighten conditions and add instrumentation until it fires or three rounds fail; only then ask for the missing evidence instead of theorizing from code.
2. When the red loop does not already point at the cause, read the failing path's history (`git log -S`, blame, bisect), then write three to five falsifiable hypotheses with predicted observations. Test one variable at a time (a debugger, then logs tagged `[DEBUG-xxxx]`), taking the split that eliminates the most candidates. Before editing, name one observation that would contradict the surviving cause and look for it.
3. When two fixes resting on one premise fail the same loop, test the premise before a third fix: a contradicted premise sends you back to the hypotheses; a confirmed one means the fixes treated a consequence, so ask the next why.
4. An architectural cause goes to the spec-first path. Otherwise turn the minimized repro into a regression test at the public seam, committed failing before the fix when that is cheap, and make the smallest change that turns it green. A test that stays green with the fix reverted, asserts only that a mock was called, or depends on timing is not the regression test. A change the evidence did not motivate is reverted.
5. Grep for the same fault elsewhere and fix every instance that shares the root cause, each with its own red case: a sibling left behind returns as the next ticket. When the history from step 2 or this sweep shows a cluster of bugs in one flow's states, offer `state-model` as `coding` says, because the next local fix will not close it.
6. Verify: run the regression test and the affected suite on the surface the user saw, then remove every `[DEBUG-xxxx]` probe and throwaway artifact.

**Reply:** what was broken, the root cause, the fix, and the failing-then-passing output; when the deciding fact took a deep dig, the always-on signal that would have shown it at first look, as a follow-up.
