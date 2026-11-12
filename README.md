# pi-anchorloop

[繁體中文](README.zh-TW.md)

**Agent workflow skills and loop extensions for [pi](https://github.com/earendil-works/pi): every task enters through its own skill, picks a playbook, and runs one shared loop, Align → Anchor → Act → Verify.**

**[Documentation](https://wayne930242.github.io/anchorloop/)** in English and [Traditional Chinese](https://wayne930242.github.io/anchorloop/zh-tw/): concepts, skills, merge trains, and every extension behavior. It also covers [using anchorloop with pi-straw-boss](https://wayne930242.github.io/anchorloop/guide/with-straw-boss/).

## Why

- **An anchor before the first change.** Each task names the exact check that observes its result, then acts in small increments and reports what the check saw.
- **A book that reads evidence.** The loop's phase comes from edits, check results, reviews, and landings, not from what the agent says.
- **Friction becomes rules.** An instruction that misled a run is recorded and fixed at its root by `solid-loop`.

## Skills

```text
anchorloop            core loop · principles · playbooks: autonomous-run, pause, pickup
├─ answering        explain · compare
├─ investigating    research · diagnose
├─ inspecting       diff-review · qa-release
├─ coding           bug-fix · feature · refactoring · perf · prototype · state-model  (+ Mini SDD)
├─ integrating      receive-car · train · urgent-car  (+ seams)
├─ deploying        deploy · rollback
├─ writing          draft · tighten · comments · pr-description
├─ visual-designing compare · refine · motion  (+ canvases, measure script)
└─ solid-loop       apply-friction · author-skill · bootstrap
shared              grilling · domain-modeling · human-feedback (uat) · agent-terse
```

## Extensions

| File | What it does |
| --- | --- |
| `pi/book.ts` | The loop book: opens loops, reads evidence, computes phases, shows the status widget, tracks units and landings, resumes a handed-off book. |
| `pi/anchor-gate.ts` | Warns once when an edit starts the act phase before an earlier phase is complete. |
| `pi/decision-tool.ts` | The `anchorloop_decision` tool: a decision trail TSV for runs the user reviews later. |
| `pi/second-thought.ts` | Asks Jev to check the phase machine's reading when a run settles; advisory only. |
| `pi/validate-tool-use.ts` | Validates skills, instruction files, and specs after each edit. |
| `pi/ttsr.ts` | Time Traveling Stream Rules: a rule fires when the agent's own output matches it. |

## Install

```bash
pi install npm:pi-anchorloop
pi install npm:pi-better-show   # optional: review pages for human-feedback and visual-designing
```

## Quick start

1. Give pi a task; it picks the entry skill whose description matches.
2. Read the opening `Alignment:` line and correct a misreading right away.
3. The first `todo` opens a loop; the widget below the editor shows its phase, and `anchorloop_stage read` shows it in full.
4. Read the reply: it carries what the anchor observed, and anything it did not exercise is `unknown`.

## Develop

```bash
uv run python hooks/validate_all.py .   # skills, rules, and durable specs
uv run --with pytest pytest -q          # validators and the pi extensions (needs node)
cd site && npm ci && npm run check && npm run build   # the documentation site
```

## Acknowledgments

- [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT), mirror revision `e44668c` of [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack) (the 2.8.0 engineering-standard additions from cursor/plugins `c742dd6`), and its port [pstack-claude](https://github.com/michael-denyer/pstack-claude) by Michael Denyer (MIT): task-type playbooks, named principles, the lifecycle playbooks, the decision trail, the closed review gate, fresh-subagent hand-off, and evidence grades; the `state-model` playbook adapts the `statechart` skill (cursor/plugins `a5539b15`).
- [google-research/harness2](https://github.com/google-research/harness2) (Apache-2.0), revision `1cfe254`: solid-loop's placement test, cheapest-mechanism order, and declining a lesson without a before/after contrast.
- [mattpocock/skills](https://github.com/mattpocock/skills) (MIT): grilling, domain-modeling, the diff review, the prototype playbook, and the feature playbook's interface checks.
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (Apache-2.0), revision `bad48a0`: the terse voice in `agent-terse`.
- HumanLayer's [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me) (MIT): the views in `answering`.
- [oh-my-pi](https://github.com/can1357/oh-my-pi): Time Traveling Stream Rules.

Ported files credit their sources in their own footers.
