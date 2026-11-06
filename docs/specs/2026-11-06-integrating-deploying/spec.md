Status: proposed
Proposed from: boss decisions 2026-11-06 (see `decision.md`); the skills' wording awaits the boss's read of branch `feat/integrating-deploying`.

# Spec: integrating and deploying

## Behavior

### Entry skills

- `integrating` triggers on reviewed work entering a shared integration branch with other work: batching cars into a train, assembling and gating, merging, a red integration branch, an urgent or fix-forward car. Its anchor is the full gates green once on the exact merged head, review P0=0 P1=0 on that head, every car's approval quoted, and the merge read back with the integration branch as target. Playbooks: `receive-car`, `train`, `urgent-car`.
- `deploying` triggers on shipping to a target, a train's deploy or UAT stage, rsync or Ansible to a host, a rollback, or checking the running version. Its anchor is each target running the shipped version as `Deploy verify` shows it, after the tests, with each target's approval quoted or the target `auto`. Playbooks: `deploy`, `rollback`; the UAT stage is a section that runs `human-feedback`'s uat playbook.
- Both run the anchorloop loop. A train runs the app's `stages` in order: `merge` (integrating), `deploy` and `uat` (deploying).

### Seams

Six, defined once in `skills/integrating/references/seams.md`:

| Seam | Decides | Default when unbound |
|---|---|---|
| Handoff route | How a slip reaches the owner and the answers return | The session is its own coordinator and owner; no other coordinator is awaited |
| Batch owner | Who assembles, gates, merges, deploys; how it is named and closed | The session, in a worktree `train-<code>` beside the repository |
| Approval | Who authorizes a merge and each deploy target; how the words reach `auth` | The user, asked once per round naming the branch and every target; every target `strict` |
| Record | The ledger | `scratch/trains/<app>.json` under the git root, machine-local, kept out of commits |
| Escalation route | `blocked`, `idle`, and announcement of a deploy the owner starts | The session says it to the user; no announcement |
| Settings | `base`, `stages`, `targets`, `maxCars`, `maxWaitMin`, project skill name | The project's instructions; unnamed: remote default branch, `merge` only, no target, 4, 60, and a missing project skill is `blocked` |

### Binding form

A host adds one block to the session's instructions (the project's instructions may hold it too). Each line names a seam and its mechanism; an unnamed seam keeps its default:

    ## Seam bindings
    - Handoff route: <mechanism>
    - Batch owner: <mechanism>
    - Approval: <mechanism>
    - Record: <path or mechanism>
    - Escalation route: <mechanism>
    - Settings: <mechanism>

A binding whose mechanism the session cannot reach is a blocker reported through the escalation route; the default does not silently replace it.

### Contract kept from the source

- The project skill heading table, with the required set (`Light checks`, `Full gates`, `Merge`, plus `Deploy` and `Deploy verify` for a `deploy` stage and `UAT` for a `uat` stage); a missing required heading stops departure with `blocked`.
- The car slip with its seven lines, and the receive-check.
- Departure (`maxCars` 4, `maxWaitMin` 60, `Load`, pipeline not red), assembly (`merge --no-ff` in arrival order, plain conflicts logged, semantic conflicts back to the later car), the fresh-context review of the train, `Full gates` once, `pre-dev/<code>` pushed only after green, red handling by dropping the guilty car, a delta recheck on every head change.
- The urgent lane and the fix-forward car (named red pipeline checked latest and red, `author's read`, next train alone, full review of the whole diff and of the one-fix scope, a full review per new SHA until one passes).
- Per-target approval (`auto`, `strict`), serialization per target, `Deploy verify` as the version running on the target, rollback, UAT on the deployed result, and the landed notice.

### What stays host-specific

The relay and its reasons, the owner's naming and its open and close, the config file, the ledger path in the host's state folder, the clash check for an announced deploy, a switch that turns the train off, and the host-side prompts for coordinators. A host binds these through the block above.

## Release

2.10.0 in `package.json`, `pyproject.toml`, and `uv.lock`. No tag, publish, or release in this change.
