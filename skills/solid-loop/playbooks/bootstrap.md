# Bootstrap

**You own an agent system built from evidence, not guesses.**

1. Pick two to four investigation targets with falsifiable objectives: build and test reality (run the suites, typecheckers, linters), an architectural seam (trace one core flow end to end), and conventions (module structure, configuration, dependencies).
2. Dispatch one isolated worker per target through `investigating`. Each returns its friction notes (`Led by`, `Found`) instead of invoking `solid-loop`.
3. Merge notes whose `Found` lines state the same fact.
4. Apply the merged notes in one [apply-friction](apply-friction.md) pass.

**Reply:** workers dispatched and their targets, each note with its action, and the components created or updated.
