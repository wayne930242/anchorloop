---
name: investigating
description: Use when researching questions, diagnosing root causes without fixing them, or gathering evidence.
---

# Investigating

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is the exact question and its completion boundary: answered, or the missing evidence named precisely.

1. Gather evidence through the playbook below that fits the question.
2. Cross-check material claims. When sources conflict, report both with citations unless a run settles it; evidence about a neighboring subject is not an answer.
3. Grade each material claim by its strongest evidence: asserted, cited
   (a `file:line` or primary source you opened this session), reasoned (the
   failure path walked and shown not to reach), executed (a script or test
   against the real code), or reproduced (observed in the running system). A
   claim a subagent relayed stays `asserted` until you open its cited line or
   rerun its command. A claim with no evidence is `unknown`, with the queries
   and sources tried beside it, so the next reader skips the empty search.
4. Report the reasoning chain with each material claim's source and grade beside it.

## Playbooks

- [research](playbooks/research.md): how something works, what is true, or why it was built this way.
- [diagnose](playbooks/diagnose.md): why a running system misbehaves, when the deliverable is a diagnosis rather than a fix.
