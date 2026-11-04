# Diagnose

**You own the diagnosis.** The deliverable explains the symptom; a fix goes to the `coding` bug-fix playbook.

1. Observe the symptom first through logs, metrics, traces, a profile, or a reproduction, before forming a theory from code. Reduce a large capture (log, profile, trace, heap snapshot) by script or subagent into a queryable form and read the reduced finding, because a raw dump overflows the lead's context.
2. Write the candidate causes with the observation each predicts, and rule them out one at a time against runtime evidence.
3. Confirm the surviving mechanism by a prediction that would fail if it were wrong.

**Reply:** the symptom as observed, the mechanism with its evidence grade, the causes ruled out and how, and what a fix must change.
