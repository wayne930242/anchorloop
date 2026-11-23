---
name: human-feedback
description: Use when evaluating human feedback, conducting interactive UI verification, or running UAT (驗收), where a person checks screenshots of an e2e flow in a web app, desktop app, or terminal before the change is accepted.
---

# Human Feedback

Turn a person's reaction to working output into an evidence-backed root cause and a correction made at that root.

## 1. Enter

- **Detected:** a person reacts to working code, design, or documentation. Invoke on the reaction itself, before answering it.
- **Invited:** verification covers UI or a human-use scenario and the user accepted a feedback pass. When screenshots can show the result, run [uat](playbooks/uat.md); otherwise name the real interface and the flows to operate, then collect what the person observed.

Route a crash or reproducible failure to the `coding` bug-fix playbook and a request for new behavior to its feature playbook. A reaction with no identifiable target may be venting; ask whether the user wants it investigated.

## 2. Diagnose

Attend to the person's problem ahead of the fix they propose, and name separately: the experience and the need left unmet; the friction that turns it into negative feedback; the decision (behavior, design, or wording) that creates the friction; the standard or precedent it violates. Use `investigating` for substantial research. When the causal decision and violated standard lack evidence, classify the reaction as a preference rather than invent a defect. Justification added to a response or document is a workaround signal: it manages the friction while leaving its source intact.

**Complete when:** the chain `feedback → experience → friction → root cause → correction` is evidence-backed.

## 3. Correct at the source

Propose the smallest correction that removes the friction where it originates, phrased as observable expected behavior. When wording creates the friction, rewrite it to state that behavior directly; when behavior or design does, correct the source and align the document. The correction lands on the causal decision, so the friction cannot return through a sibling path, and follows the pattern and layer that already govern that source; a guard or fallback that masks the root belongs in the root instead. Use `grilling` when the alternatives carry a user-owned trade-off; otherwise state cause and correction and continue.

## 4. Hand off

Return the confirmed chain as decision input to `coding` for a source fix, or to `writing` for a document fix. When the feedback conveys a preference or convention rather than an isolated bug, hand it to `reflecting-to-root` where the user's root installs that skill, else place it by `solid-loop`'s Placement. A correction of a mistake an instruction already forbids is a repeat: invoke `solid-loop` to raise its enforcement.
