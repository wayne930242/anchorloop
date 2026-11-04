# Durable phases and artifacts

The Durable threshold lives in [SKILL.md](SKILL.md).

Artifacts live in `docs/specs/YYYY-MM-DD-<slug>/`. Create each file when its phase is reached, not up front. Link to instructions, ADRs, code, and tickets rather than copying them.

## Decision → `decision.md`

Resolve facts from their source; use `investigating` or `inspecting` when search is wide. Invoke `grilling` with `decision.md` only when it has an `open` row. Before implementation, note core-rule readiness in `decision.md`.

The file holds outcome and actors; in and out of scope; concrete scenarios; confirmed decisions; open consequential decisions. Explore every consequential branch in:

```markdown
| Question | Answer | Basis | Status |
|---|---|---|---|
| ... | ... | request, evidence, or decision link | grounded, confirmed, or open |
```

`grounded` comes from the request, source facts, or existing decisions; `confirmed` comes from the user; `open` is a consequential user-owned decision.

**Complete when:** no open row blocks observable behavior.

## Spec → `spec.md`

Persist the spec in `spec.md` under `Status: proposed`, then have a fresh-context subagent read it and its links, restate the contract, and list each point it would have to guess to build it. Fold each guess into the spec or add it to `decision.md` as an `open` row, because the author cannot see assumptions it never wrote; rerun the reader once when a fold changes observable behavior. Then present it for explicit user confirmation. `proposed` keeps production source untouched while artifacts and read-only work stay open. Only the user's approving reply sets `Status: approved`, `Approved at`, and `Approved from`.

The file opens with the approval header, then observable behavior and edge cases; compatibility constraints and non-goals; applied standards with their impact; evidence and precedent links; the selected reality anchor and checkpoint.

```markdown
Status: proposed | approved
Approved at: <date the user approved, empty while proposed>
Approved from: <the user reply that approved it, empty while proposed>
```

## Design → `design.md`

Choose the smallest approach that fits the approved spec and architecture. Follow the matching playbook's design steps ([feature](playbooks/feature.md) for interfaces and seams, [prototype](playbooks/prototype.md) when a named question is cheaper to settle by experiment) and the project's exact skill.

The file holds the chosen approach; interfaces and data flow affected; existing precedent; decisions, trade-offs, and risks, with at least one rejected alternative or the reason none exists; the method selected inside the reality anchor.

**Complete when:** implementation invents no product behavior or architecture.

## Verify → `verification.md`

Review the diff against project standards, the approved spec, and the confirmed domain model; dispatch a verification agent when the anchor needs an independent observer. Give every requirement in `spec.md` its own row:

```markdown
| Requirement | Evidence | Result |
|---|---|---|
| Observable behavior from spec | Real interface executed and the specific output observed | pass / fail / unknown |
```

- **pass**: The anchor ran against the actual implementation and observed the expected behavior.
- **fail**: The anchor observed a deviation from the spec or an error.
- **unknown**: No anchor exercised the requirement in this run.

Then human appropriateness verdicts; deviations from the approved spec or design; unresolved verification gaps and their impact. When the loop book holds friction, include a Reflexive section listing each entry with its class (`misdirection`, `gap`, or `resolved`) and its action.

## Updates

Update the owning phase file when new information changes it. A new consequential decision returns to `decision.md`; a change to user intent or observable behavior returns to Spec and user confirmation.

---

The fresh-reader spec check is adapted from the Goldfish comprehension review in [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) (Apache-2.0), revision `a8380ab`, `agents/comprehension.md`.
