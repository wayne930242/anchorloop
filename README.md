# pi-anchorloop

[繁體中文](README.zh-TW.md)

**Agent workflow skills for [pi](https://github.com/earendil-works/pi): every task enters through its own skill, picks a playbook, and runs one short loop: state the check, change, show it passing.**

**[Documentation](https://wayne930242.github.io/anchorloop/)** in English and [Traditional Chinese](https://wayne930242.github.io/anchorloop/zh-tw/): concepts, skills, merge trains, and every extension behavior. It also covers [using anchorloop with pi-straw-boss](https://wayne930242.github.io/anchorloop/guide/with-straw-boss/).

## Why

- **An anchor before the first change.** Each task writes `Anchor: <check>` before its first edit and ends with a passing run of that check after its last change.
- **A reviewer on another model.** Authorization, migrations, shared contracts, security, or two or more workers bring one fresh reviewer on a different model family; P0 and P1 block the merge.
- **No turn tax.** No phase machine, no stage tools, and no advisory turns: one close guard adds a single line when a run settles without a passing anchor run.

## Skills

```text
anchorloop            loop card · playbooks: autonomous-run, pause, pickup
├─ answering        explain · compare
├─ investigating    research · diagnose
├─ inspecting       diff-review · qa-release
├─ coding           bug-fix · feature · refactoring · perf · prototype · registered-flow · state-model  (+ Mini SDD)
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
| `pi/close-guard.ts` | Adds one line when a run settles after a file change with no passing run of its anchor since; never starts a turn. |
| `pi/validate-tool-use.ts` | Validates skills, instruction files, and specs after each edit. |

3.0.0 removed the loop book, the anchor gate, the decision tool, second thought, and stream rules; [docs/migration-3.0.md](docs/migration-3.0.md) lists what to change.

## Install

```bash
pi install npm:pi-anchorloop
pi install npm:pi-better-show   # optional: review pages for human-feedback and visual-designing
```

## Quick start

1. Give pi a task; it picks the entry skill whose description matches.
2. Read the opening goal line and correct a misreading right away.
3. Read the `Anchor:` line: the exact check that will observe the result.
4. Read the reply: it carries a passing run of the anchor after the last change, and anything it did not exercise is `unknown`.

## Develop

```bash
uv run python hooks/validate_all.py .   # skills, rules, and durable specs
uv run --with pytest pytest -q          # validators and the pi extensions (needs node)
cd site && npm ci && npm run check && npm run build   # the documentation site
```

## Acknowledgments

- [pstack](https://github.com/backnotprop/pstack) by Lauren Tan (MIT), mirror revision `e44668c` of [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack) (the 2.8.0 engineering-standard additions from cursor/plugins `c742dd6`), and its port [pstack-claude](https://github.com/michael-denyer/pstack-claude) by Michael Denyer (MIT): task-type playbooks, the lifecycle playbooks, the closed review gate, fresh-subagent hand-off, and evidence grades; the `state-model` playbook adapts the `statechart` skill (cursor/plugins `a5539b15`).
- [google-research/harness2](https://github.com/google-research/harness2) (Apache-2.0), revision `1cfe254`: solid-loop's placement test, cheapest-mechanism order, and declining a lesson without a before/after contrast.
- [mattpocock/skills](https://github.com/mattpocock/skills) (MIT): grilling, domain-modeling, the diff review, the prototype playbook, and the feature playbook's interface checks.
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (Apache-2.0), revision `bad48a0`: the terse voice in `agent-terse`.
- HumanLayer's [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me) (MIT): the views in `answering`.

Ported files credit their sources in their own footers.
