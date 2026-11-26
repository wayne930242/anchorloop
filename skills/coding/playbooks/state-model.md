# State model

**You own the rules of a flow that moves between states: each holds on every path or has a replayed bug path.** Run it when the user takes `coding`'s offer for a flow whose rules turn on how actors' retries, restarts, or timeouts interleave, such as a job lifecycle, a handoff, a deploy gate, or a protocol.

1. Name the reader (who decides whether the behavior is right), the actors, and the rules in the reader's sentences, such as "a paid order is never lost". A rule the reader has not agreed to is a question; with no reader present, a rule the code already enforces in the plain sequential case counts as agreed and the rest are marked proposed. For each actor, name where its steps come from (code, a prompt, a person's habit); a step an agent would improvise stays out of the model and goes in the reply. Find the project's test rig and name the model's steps after what it can drive; a step the code does not tell apart is not a step.
2. Spec: write a TLA+ spec, its configs, and the view module. A flow that outlives this change keeps them beside its code under version control, with a README table of each config's result and the committed `chart.mmd` and `report.md` of the small and family checks (no `tlc.out`); a one-off investigation keeps them in a scratch folder. Keep a small config that draws whole (one of everything, no failure steps): the chart the reader confirms. Size and split the check configs as [state-model-checks](../references/state-model-checks.md) says; configs that differ only in constants come from one script that reruns them all.
   - Each agreed rule is an `INVARIANT`. A rule about what an actor emitted reads a variable holding the last step's emitted value.
   - "Always ends a certain way" becomes: in every state where no actor still has a step for it, the outcome holds; write "an actor still has a step" as its own definition. When stopping anywhere is fine, set `CHECK_DEADLOCK FALSE`.
   - Model the steps that interleave, failing ones included (retry, restart, timeout, a second actor); one step is one thing another actor can come between. Keep constants small.
   - Each guard and suspected cause is a BOOLEAN constant. A decided design not yet built is a constant `Design` (`today`, `decided`) and a set `Fixes`, so one spec checks the code and the design.
3. Check: read the `statechart` skill's `SKILL.md` by path (usually `~/.agents/skills/statechart/SKILL.md`; the user's root installs it, anchorloop does not ship it) and run `~/.agents/skills/statechart/scripts/statechart SPEC.tla --config FILE --view view.mjs --out DIR`. It exits 1 when a rule breaks and still writes the report, and refuses a non-empty `DIR`. When it is absent, say so and stop at the spec.
   - The report gives the shortest path per broken rule and can hide other causes: switch that cause off and rerun until the rule holds.
   - For each rule that holds, change the spec once the way wrong code would behave and watch it break; a rule no change breaks was not checked.
   - With a design modeled, run `Fixes` whole, then each fix left out (`without/Pn`): a fix whose removal breaks nothing is not needed.
   - After the first report, read every step against the code once more.
4. Replay: turn each violating path into a test on the real code and run it red for the modeled reason, asserting the rule at the end in the reader's words. Replay an interleaving by pausing one request at the step boundary the model names, with a green control test of the same steps without interleaving. A path that does not reproduce means the model is wrong until shown otherwise.
5. Show: write the small chart, each rule with its result, and each path with its red output into a page in the reader's language and open it with `show_doc` and `view: "page"`; the reader confirms the flow and rules before any production change, and a corrected rule goes back to step 2.
6. Fix until each replay test is green, update the spec to the fixed behavior, and rerun until every rule holds. When fixes are out of scope, the replay tests stay red on an unmerged branch, one ticket per bug naming its test.

**Anchor:** the TLC report, where every rule holds and was shown able to break, or each broken rule has a replay test run red, then green after the fix or parked in a ticket.

**Reply:** the rules, each bug path in the reader's sentence, what the model leaves out, and the command that reruns the configs.

---

Adapted from pstack `statechart` by Lauren Tan (MIT License), cursor/plugins revision `a5539b15a3d56e04992565aafee2b37051329ce3`, path `harness/pstack/claude-code/skills/statechart`.
