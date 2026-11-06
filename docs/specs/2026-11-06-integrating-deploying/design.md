# Design: integrating and deploying

## Layout

```text
skills/integrating/  SKILL.md · references/seams.md · playbooks/{receive-car,train,urgent-car}.md
skills/deploying/    SKILL.md · playbooks/{deploy,rollback}.md
```

`integrating/references/seams.md` is the one home of the seam vocabulary, defaults, settings keys, and ledger; `deploying` links to it. The heading table lives only in `integrating/SKILL.md`. Skills stay far below the 300-line limit.

## Source mapping

Source files, read only: `P` = `pi-straw-boss/prompts/integrator.md` at `47b91ba`, `A` = `prompts/apps-config.md` (Merge train section and `integration` fields), `L` = `prompts/planning.md` (integration block, line 37), `H` = `docs/how-it-works.md` (Merge train), `T1` = `docs/specs/2026-10-30-merge-train.md`, `T2` = `docs/specs/2026-11-05-train-stages.md`, `D` = `weihung-basic-agent/rules/deployment.md`. `I` = `skills/integrating`, `Dp` = `skills/deploying`.

### `P` (integrator.md)

| Source | New home |
|---|---|
| Intro: one main takes the coordinators' cars through `merge`, `deploy`, `uat` | `I/SKILL.md` Stages |
| Intro: "a main, not the tower" | host-specific (owner's role in the host) |
| Intro: the project skill holds every concrete check; read its headings; add nothing it does not say | `I/SKILL.md` Project skill contract |
| Intro: a missing `Light checks`, `Full gates`, `Merge`, or a declared stage's heading means do not depart, report `blocked` naming the config error | `I/SKILL.md` Project skill contract (closing paragraph); escalation route in `seams.md` |
| Rules 1: no merge without a quote of the authorization covering the integration branch | `I/SKILL.md` Rules 1; `I/playbooks/receive-car.md` steps 1, 2 |
| Rules 1: `auto`/`strict` targets, unlisted `strict`, `auto` is the standing word | `I/SKILL.md` Rules 1; `seams.md` Settings keys |
| Rules 2: only the owner merges and claims `pre-dev/<code>` | `I/SKILL.md` Rules 2 |
| Rules 2: own merges, pushes, merge-triggered deploys need no call; a self-started deploy announces its target | `I/SKILL.md` Rules 2; `Dp/playbooks/deploy.md` step 4; `seams.md` Escalation route |
| Rules 3: rename to `integ <project>`, never again | host-specific (batch owner binding) |
| Rules 3: ledger with car, tickets, SHAs, stage, deployed versions, UAT verdicts; one todo per train | `seams.md` Record and Ledger; `I/SKILL.md` Rules 3 |
| Receiving a car: slip block | `I/playbooks/receive-car.md` step 1 |
| Receiving a car: the five checks and the return of a failing car | `I/playbooks/receive-car.md` step 2 |
| Receiving a car: answer with train number and departure conditions | `I/playbooks/receive-car.md` step 3 |
| Departure: `maxCars` 4, `maxWaitMin` 60, every coordinator arrived, `Load` (omitted: 1-minute load vs cores), pipeline not red (a fix-forward car excepted) | `I/playbooks/train.md` step 1; `seams.md` Settings keys |
| Assembly: `train/<code>` from the latest base in a worktree, `merge --no-ff` in arrival order, plain conflicts resolved and logged, semantic conflicts back to the later car, run `Train assembly` | `I/playbooks/train.md` step 2 (worktree location: batch owner default in `seams.md`) |
| Review: fresh-context reviewer on `train/<code>` for interactions, conflict resolutions, migration order; P0/P1 of one car back to it, of assembly the owner fixes | `I/playbooks/train.md` step 3 |
| `Full gates` once per train; green then `Merge`, `Post-merge`; push `pre-dev/<code>` only after green; no force push | `I/playbooks/train.md` step 4 and opening line |
| Red: find the guilty car per `Full gates`, drop, rebuild; tell the coordinator car, failing tests, log path, `train` SHA; session gone means `blocked` | `I/playbooks/train.md` step 5 |
| Every head change (dropped car, post-push `git revert -m1`) re-runs `Train assembly`, a delta recheck, `Full gates`; after a revert, before `Merge` | `I/playbooks/train.md` step 6 |
| `urgent` only on the approver's "first", a P0 defect in a live target, or a fix-forward car; still reviewed and gated | `I/playbooks/urgent-car.md` step 1 |
| Fix-forward car (as tightened in `47b91ba`): only the fix of the branch's red pipeline, which the owner checks is the latest and red else returns the car; slip `review` reads `author's read`; departs as the next train, alone, red or not, once `Load` allows; interrupts a running gate only if `Urgent lane` says so; the reviewer's full-depth review also checks the car holds only that fix (more means returned); each new SHA gets the full review until one passes; other report-less cars returned | `I/playbooks/urgent-car.md` steps 2 to 4; `receive-car.md` steps 1, 2; `train.md` step 1 |
| Deploy: `Deploy` per `auto` target and per slip-named target in the skill's order | `Dp/playbooks/deploy.md` step 1 |
| Deploy: a `strict` target needs `auth` on every car; else skip, ask, a held car is not landed, held before `Merge` leaves like a dropped car; ask before `Merge` where merging deploys a `strict` target | `Dp/playbooks/deploy.md` step 2 |
| Deploy: one train per target; later `Merge` waits where merging deploys | `Dp/playbooks/deploy.md` step 3 |
| Deploy: what the skill adds per target, then `Deploy verify`; done is the target running the train's own version; green job, accepted request, finished monitor are not done | `Dp/playbooks/deploy.md` steps 5, 7 |
| Deploy: a failed target follows `Deploy` (rollback, retry) and its car goes back as a red one | `Dp/playbooks/rollback.md` steps 2, 4 |
| UAT: after `Deploy verify`, run `UAT` for `uat` cars on the deployed result | `Dp/SKILL.md` UAT stage, lead |
| UAT: one page per train, one `review` block, label and body, opened with `show_doc` once ready, blank box accepted | `Dp/SKILL.md` UAT stage bullet 2; `human-feedback` uat playbook step 4 |
| UAT: a later train may deploy meanwhile; captures are the record | `Dp/SKILL.md` UAT stage bullet 3 |
| UAT: a comment returns the car with comments, captures, version; `UAT` says whether to revert first; a revert goes as its own train; the fix returns as a new car recapturing commented (or all) checkpoints | `Dp/SKILL.md` UAT stage bullet 4; `Dp/playbooks/rollback.md` step 5 |
| After the train: "landed in `<version>`, your commit is `<sha>`", plus "accepted in UAT"; the coordinator closes its ticket | `I/SKILL.md` After the train |
| After the train: idle report when queue empty, no stage runs, no UAT page waits; the host closes the owner | `I/SKILL.md` After the train; `seams.md` Escalation route |

### `A`, `L`, `H`, `T1`, `T2`

| Source | New home |
|---|---|
| `A` principle paragraph; `H` Principle bullet; `L` integration block (coordinator's anchor, gates once on the integrated head, exceptions, `human` anchor is the train's UAT, the train replaces the merge-time checkpoint and not the fresh review) | `I/SKILL.md` Principle |
| `A` heading table, the three required headings, the stage headings, missing heading means `blocked` | `I/SKILL.md` Project skill contract (all ten headings verbatim) |
| `A` `integration` fields: `skill`, `maxCars`, `maxWaitMin`, `base`, `stages`, `targets`; `auto` set only by the approver with words quoted in the commit | `seams.md` Settings keys; the config file itself is host-specific |
| `A`/`H` switch that turns the train off | host-specific |
| `H` Hand-off and routing (relay, forwarding to the one owner, opening and closing it) | host-specific: handoff route and batch owner bindings |
| `H` Integrator (owns `pre-dev`, assembles locally, one review, gates once, pushes only green, ledger, name, "exception to never merge into an integration base") | covered by `train.md` and `seams.md`; the last clause and the name are host-specific |
| `H` Stages | `I/SKILL.md` Stages; `Dp/playbooks/deploy.md` |
| `T1` Q4 (coordinator closes tickets; owner only when the session is gone), Q5 (each car keeps its review, the owner adds one of the merged result), Q7 (an urgent car does not interrupt a gate unless the skill says so) | `I/SKILL.md` After the train, Principle; `I/SKILL.md` contract row `Urgent lane`; `urgent-car.md` step 2 (Load and red-pipeline conditions still hold) |
| `T2` Why: an older pipeline deployed after a newer one | `deploy.md` step 3 |
| `T2` Why: a merge gated on a monitor finishing, not on the run's conclusion | `train.md` step 4; `deploy.md` step 7 |
| `T2` Why: a healthy rollout reverted by a health deadline | `rollback.md` step 1 (a healthy report is not the proof; read the version) |
| `T2` Why: captures taken before the merge, not on the integrated result | `Dp/SKILL.md` UAT stage lead |
| `T2` D5: a `uat` car counts as landed only after acceptance | `Dp/SKILL.md` UAT stage, last bullet |

### `D` (deployment rules)

| Rule | New home |
|---|---|
| `rsync --delete` only after verifying runtime-file exclusions | `Dp/SKILL.md` Rules 1 |
| Run the project test suite before any deploy | `Dp/SKILL.md` Rules 2 (in a train, `Full gates`) |
| Ansible `--check` first on production targets | `Dp/SKILL.md` Rules 3; `deploy.md` step 5 |
| Target directory exists and is non-empty before a destructive sync | `Dp/SKILL.md` Rules 4 |

The rules file becomes one line: `Deploy work follows the `deploying` skill's Rules.`

## Host-side follow-up (not done here)

1. The host drops the generic procedure from its integrator prompt and keeps the host-specific items above, loading `integrating` and `deploying` instead.
2. The host's session prompt gains a `Seam bindings` block. For a relay-and-owner host it reads, in outline:
   - Handoff route: the slip goes to the relay with reason `shared`; the relay forwards it to the project's one owner; answers return by direct message.
   - Batch owner: the project's one integrator session, named by the host's rule, opened and closed by the relay; worktrees at `~/.herdr/worktrees/<repo>/train-<code>`.
   - Approval: the boss; `auth` quotes the boss's words; questions go through the question tool.
   - Record: the host's trains folder, `<project>/<app>.json`.
   - Escalation route: the relay with reasons `blocked` and `milestone` (idle); an announced deploy goes with reason `shared` naming the target.
   - Settings: the host's `apps.json` (`integration` fields).
3. The shared rules file's deployment text is replaced by the one-line pointer.
4. A project integration skill (moldplan-center `integrate`) gains one line under its title: "Run under anchorloop `integrating` (merge) and `deploying` (deploy, UAT); this file holds only the headings they read." Its Light checks slip source becomes `integrating/playbooks/receive-car.md`.
