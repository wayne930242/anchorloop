# ADR Format

ADRs live in `docs/adr/` as `0001-slug.md`, numbered one above the highest existing; create the folder with the first ADR.

```md
# {Short title of the decision}

{1-3 sentences: the context, what we decided, and why.}
```

An ADR can be one paragraph. Add a `Status` (`proposed | accepted | deprecated | superseded by ADR-NNNN`), `Considered Options`, or `Consequences` section only when it adds value.

Offer an ADR only when the decision is all three: hard to reverse, surprising without context, and the result of a real trade-off. Typical cases: architectural shape, integration patterns between contexts, technology with lock-in, boundary and ownership decisions, deliberate deviations from the obvious path, constraints the code does not show, and rejected alternatives someone would otherwise propose again.
