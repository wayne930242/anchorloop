# QA and release readiness

**You own the findings ledger.** Use an active `docs/specs/` `verification.md` as the ledger; otherwise the project's QA convention, or `docs/qa/discover-qa-YYYY-MM-DD.md` when findings must persist.

1. Discover: record the scope, version or branch, environment, and primary flows, then every unexpected behavior with reproduction steps. Cover only the edges that matter here: errors, boundaries, concurrency, permissions, data consistency. Discovery ends when every declared flow was exercised and every observation is in the ledger.
2. Resolve each finding: trace it to a falsifiable root-cause hypothesis, hand a source fix to `coding` with the finding and repro as decision input, and take the anchor evidence it returns as the re-check. Record the evidence or the unresolved gap before the next finding.
3. Commits and pushes belong to the workflow that authorized them.

**Reply:** discovered, resolved, and deferred findings with evidence and owner. QA passes only when no unresolved finding contradicts the release criteria.
