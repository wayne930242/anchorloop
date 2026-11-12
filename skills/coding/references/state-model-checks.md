# State model: configs and `statechart` notes

Read by the `state-model` playbook at steps 2 and 3. The `statechart` command caps the chart at 500 model states and, once a rule breaks, caps each rerun at 100,000 distinct states, leaving the rest under "Rules not checked".

## Configs

- **Small:** one of everything, no failure steps, the chart the reader confirms. Variables added for rules count against the budget: switch off the steps that set them, or give TLC a `VIEW` that leaves out the ones that decide nothing there (an arrow can then lead to the representative state; say so in the config). In a regions chart, leave out a region every step flips; the rules about it still mark the states where they break.
- **Family:** when one full config passes about 100,000 states, split it by failure family or cause (two operators at once, the same request twice, one request with undo and sync failure). Each stays under about 70,000 states, so every rule is checked to completion, and the README says which family checks which rule.
- **Shape:** a constant that decides the session's shape cannot be on beside its opposite, so each shape is a config.
- **Left out:** the rules a full run reports as not checked get a config without the rules that break.
- **Cause, `without/Pn`:** one config per cause switched off, and per fix left out.

## Sizing

Count states with plain TLC and the invariants off before the first `statechart` run; with `-continue` and broken invariants TLC prints every trace and looks hung. Interchangeable entities in ordered slots cost N! (2 slots to 3: 65k to 248k states); each optional actor multiplies the count; give the model the fewest slots and actors that still show the rule.

## Running `statechart`

- Exit 0: every rule holds. Exit 1: a rule broke, and the output is written. Exit 2: TLC stopped with an error or the command could not run, and nothing is written.
- `--out` must be new or empty; `tlc.out` carries times and absolute paths.
- Write `Next` as a disjunction of named actions. A step is named after the innermost definition that holds the primed variables, so `A == B(arg)` is reported as `B` (tell such steps apart in `step()` by `from` and `to`), and a `guard /\ B(x)` written straight into `Next` is named `Next` (put the guard in a named action).
- A `group()` view needs `colors`: blue, orange, purple, yellow, teal, tan, or pink.
- A regions view returns the same keys for every state.
- A hidden step on a bug path is refused; label it.
- Keep `title` to ASCII punctuation: a full-width comma or colon in it comes out garbled in `chart.mmd`, though in state labels it is escaped and renders.
- The chart's own words (`Legend`, `At the same time`, `[unless …]`, `direction LR`) are English and fixed; for a reader in another language, edit them in the page copy.
- `Rules not checked: TypeOK` follows any broken rule in a large model; leave the type invariant out of a config whose point is one rule, or check it first.
- In TLA+, `A \/ B[x]` evaluates `B[x]` even when `A` holds; guard an index with `IF`.
