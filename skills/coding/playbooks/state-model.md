# State model

**You own the rules of a flow that moves between states: each holds on every path or has a replayed bug path.** Use it when a change touches a flow with more than one actor, or with retries, restarts, or timeouts, such as a job lifecycle, a handoff, a deploy gate, or a protocol ([**Model the domain**](../../anchorloop/principles/model-the-domain.md)).

1. Align: name the reader (the person who decides whether the behavior is right), the actors, and the rules in the reader's own sentences, such as "a paid order is never lost". A rule the reader has not agreed to is a question for them, not a rule.
2. Spec: in a scratch folder outside the repository, write a TLA+ spec and its `.cfg`. Give each agreed rule an `INVARIANT`, adding the variable the rule needs when the model has none; a rule that fails is a finding, so it stays as written. Model the steps that interleave, including the failing ones (a retry, a restart, a timeout, a second actor). Keep the constants small.
3. Check: read the `statechart` skill's `SKILL.md` and run it on the spec with a view module that turns each state and step into the reader's words. `statechart` is a separate user skill that the user's root installs and anchorloop does not ship; when it is absent, say so and stop at the spec.
4. Show: write the chart and the report into a markdown page and open it with `show_doc` and `view: "page"`; the reader confirms the model matches the behavior they mean before any code changes. A correction to the model comes first and reruns step 3.
5. Replay: turn each shortest violating path in the report into a test on the real code, one step per action, and run it red for the modeled reason before any fix ([**Sequence verifiable units**](../../anchorloop/principles/sequence-verifiable-units.md)). A path that does not reproduce means the model is wrong until you show otherwise: correct the model, or record why the code differs.
6. Act: fix until each replay test is green, update the spec to describe the fixed behavior, and rerun the check until every rule holds.

**Anchor:** the TLC report, where every rule holds, or each broken rule has a red then green replay test.

**Reply:** the rules, each bug path with the reader's sentence for it, what the model leaves out, and the command that reruns the check.

---

Adapted from pstack `statechart` by Lauren Tan (MIT License), cursor/plugins revision `a5539b15a3d56e04992565aafee2b37051329ce3`, path `harness/pstack/claude-code/skills/statechart`.
