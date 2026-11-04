# PR description

**You own the reviewer's first minute.** The reader has the diff and needs the reasons. Write the text once opening the PR or MR is authorized; this playbook never opens one.

1. Why: the problem and the approach, in one to three short sentences.
2. What changed and what it deliberately leaves out, a follow-up or a known gap included.
3. What it could break: who and what it touches, and why that is safe or risky.
4. Verification: the anchor command and what it observed, then each requirement left `unknown`. Tradeoffs appear only for a rejected alternative the reviewer would ask about.
5. Link logs, SHA lists, and tables instead of pasting them. A commit body adds what the subject cannot hold and does not restate it.

**Reply:** the description text and the artifacts it links.

---

Adapted from [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT License), revision `c742dd6` of [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack), `skills/poteto-mode/playbooks/opening-a-pr.md`.
