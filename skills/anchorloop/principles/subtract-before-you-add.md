# Subtract before you add

**When:** Sizing any change.

Delete dead code, one-caller wrappers, redundant checks, and stale prose first; the smallest change that solves the problem ships. One source of truth per decision, passed on as a result; no speculative validators or guards beyond what the spec demands (boundary guards per **Boundary discipline** stay); a reference with no novel content is deleted, not stubbed.
