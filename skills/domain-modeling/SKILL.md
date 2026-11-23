---
name: domain-modeling
description: Use when project terminology or domain boundaries need refinement.
---

# Domain Modeling

Actively reconcile the user's language, the project's glossary, and code. Return
confirmed terms and decisions to the caller's artifact, or in the reply when
there is none.

## Discipline

1. Read the applicable `CONTEXT.md`; follow `CONTEXT-MAP.md` when the repository
   has multiple domain contexts.
2. Surface conflicts between the user's term, glossary definition, and code.
   Sharpen vague or overloaded terms into one canonical meaning.
3. Stress-test relationships and boundaries with concrete edge-case scenarios.
4. Check asserted behavior against code. Let the user decide when current code
   and intended domain truth disagree.
5. Record a confirmed term immediately in `CONTEXT.md`, using
   [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). Keep the glossary
   free of implementation detail.
6. Offer an ADR only when it meets the criteria in
   [ADR-FORMAT.md](ADR-FORMAT.md).

## Carry the model into code

- Use the confirmed ubiquitous language in identifiers, tests, errors, and
  public contracts within its bounded context.
- Keep domain invariants in the domain model. UI, transport, persistence, and
  orchestration layers call the model instead of reimplementing its rules.
- Translate external schemas, persistence records, and another context's
  vocabulary at explicit adapter seams; do not let them become the internal
  domain model by accident.
- Use tactical DDD patterns only when they clarify real domain rules. Reserve
  entities, aggregates, value objects, and repositories for genuine domain concepts.
- When implementation reveals a domain contradiction, bring it to the user
  before encoding it.

Create the glossary or ADR directory only when there is confirmed knowledge to
record. Domain modeling is complete when language, boundaries, invariants,
adapters, code, and tests express the same confirmed model.

---

Adapted from [mattpocock/skills](https://github.com/mattpocock/skills)
`domain-modeling` (MIT License, Copyright (c) 2026 Matt Pocock).
