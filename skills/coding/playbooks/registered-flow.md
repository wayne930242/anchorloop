# Registered flow

**You own the record's lifecycle: every status change goes through one registered definition, and nothing else writes the status.** Use it beside `bug-fix` or `feature` when a change adds, removes, or guards a transition of a record that carries a status or stage (an order, a request, a ticket, a job), or when a status changed where it should not.

1. Inventory: find every writer of the status with `ast-grep` or a grep for the field (assignments, a generic patch or admin endpoint, a batch job, SQL that updates the column) and list each with its file. Name the states, events, and guards in the reader's words; a transition the reader has not agreed to, such as an admin override, is a question for them.
2. Register: declare every transition in one definition, the project's state-machine library or transition table where it has one, else a typed table (`from`, `event`, `to`, guard) in the record's module; a new library goes through the dependency rules. One function applies an event: it looks the pair up, runs the guard, and writes status and version in one write that fails when the version moved, so two events on one record cannot both win; an event a person decides from a screen, such as an approval, carries the version they saw. Route every writer from step 1 through it and delete their own status checks.
3. Lock: a check fails when the status is written outside that function (an `ast-grep` rule or a grep of the field's assignments), run red once on a planted direct write.
4. Chart: render the definition to a Mermaid `stateDiagram-v2` committed beside it, with a test that renders it again and fails on a difference, so a transition change shows in review as a chart change. When the change adds or removes a transition the request did not spell out, open the chart with `show_doc` and have the reader confirm it before the production edit; this is the design checkpoint where `coding` offers `state-model` when its condition holds.
5. Tests from the definition: walk it for one test per registered transition, reached by the shortest path from the initial state through the public seam, and one test that sends every unregistered (state, event) pair and asserts a rejection with the record unchanged.
6. A race between two events on one record is the version check's, with a test that interleaves them at the write. When the user takes the [state-model](state-model.md) offer, carry its agreed rules back here as guards.

**Anchor:** the per-transition tests and the unregistered-pair test green, the chart check green, and the single-writer check run red on a planted write.

**Reply:** the chart, each writer routed or removed, the transitions the reader confirmed or left open, and what the table cannot show.
