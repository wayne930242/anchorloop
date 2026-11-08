# Seams

`integrating` and `deploying` run the same procedure under any host. They leave seven places open, called seams, where a host or a project decides who, where, or how. Each seam below says what its mechanism must do; an unbound seam takes its default.

## Binding

The session's instructions and the project's instructions each hold at most one block. Each line binds one seam to a mechanism; a seam the block leaves out keeps its default:

    ## Seam bindings
    - Handoff route: <how a car slip reaches the batch owner and how its answers come back>
    - Batch owner: <who assembles, gates, and merges a batch, and how it is named and closed>
    - Approval: <who authorizes a merge and each deploy target, and how their words reach the slip>
    - Record: <where the ledger lives>
    - Escalation route: <where blocked, idle, and deploy announcements go>
    - Settings: <where the integration branch, stages, targets, and thresholds come from>
    - Step runner: <how a train's steps are recorded and how a step that runs a command is started, waited on, and reported>

Read the block before the first step. When both hold a block, the session's line wins per seam; a seam neither binds takes its default. A Settings key the bound source omits takes the default below. A binding whose mechanism the session cannot reach is a blocker: report it through the Escalation route and keep the stage closed, because the default would silently move a decision to a party the host did not choose. When the Escalation route itself cannot be reached, say the blocker to the user.

## Terms

- **Car**: one reviewed branch offered to the integration branch, with its slip.
- **Train**: the cars assembled, gated, merged, and shipped together, identified by a `<code>` (date and letter, such as `2026-11-05-a`).
- **Integration branch**: the shared branch a train merges into (`base`).
- **Coordinator**: the party that answers for a car and receives the answers about it.
- **Project skill**: the project's skill that holds the heading contract in [integrating](../SKILL.md).

## The seams

| Seam | Decides | Default when unbound |
|---|---|---|
| Handoff route | How a car slip reaches the batch owner; how the train number, a returned car, and the landed notice reach the coordinator. The owner may instead hand each car's outcome to the host as a state and wait for the host's delivery report. | The session is its own coordinator and batch owner: it writes each slip into the ledger and answers itself. It awaits no other coordinator and sends each notice itself. |
| Batch owner | Who receives cars, assembles, gates, merges, and deploys, where its train worktrees live, and how it is named and closed. It may schedule trains and give each departed train to a session of its own, which then owns it to the end. | The session itself, in a worktree `<repo>-train-<code>` under the worktree root the session's instructions name, else a sibling directory of the git root. It closes when its ledger holds no open train. |
| Approval | Who authorizes a merge to the integration branch and each deploy target, and how the words reach the slip's `auth`. | The user. The session asks one question round naming the integration branch, `pre-dev/<code>` where `Merge` pushes it, `base` when Settings leave it unnamed, and every deploy target the cars list, and quotes the reply in `auth`. Every target is `strict`. |
| Record | Where the ledger lives: one file per app, or an index per app and one file per train. | `scratch/trains/<app>.json` under the git root (`<app>` is the repository's name when it has one app). It is machine-local state: stage files by name and keep it out of commits. |
| Escalation route | Where `blocked`, `idle`, and the announcement of a deploy the owner starts itself go. | The session says it in its reply to the user. The announcement goes in the reply too. |
| Settings | The integration branch, the stages, the acceptance kinds (`accept`), the targets, `maxCars`, `maxWaitMin`, and the project skill's name. | The project's instructions name them. Left unnamed: `base` is asked in the Approval round, `stages` is `merge`, `accept` is empty, no target is listed, `maxCars` is 4, `maxWaitMin` is 60, and a missing project skill is a `blocked`. |
| Step runner | How a train's steps are recorded (one per gate, merge, pipeline read, deploy, verify, and rollback), and how a step that runs a command starts, waits for `Load`, takes locks and holds (an integration branch, a target), and reports its state and outcome. | The owner's one `todo` per train, with a line per step. Each heavy check runs in the session's own shell after `Load`'s wait, and its outcome is read from its exit status and output, not from the shell having returned. |

## Settings keys

- `base`: the integration branch.
- `stages`: ordered; `merge` is first and always present, then optionally `deploy`. There is no `uat` stage: acceptance happens before handoff. A `stages` that still lists `uat` (bindings before 2.11.0) is a configuration error: the train does not depart and reports `blocked`, asking the project to move it into `accept` and rename the project skill's `## UAT` to `## Acceptance`.
- `accept`: the acceptance kinds a car must show evidence of at receipt, such as `e2e` or `uat`; empty means none. Each car's author runs them on its own branch with the approver's nod.
- `targets`: each deploy target to `auto` or `strict`. `auto` takes every train with no per-car approval, since the setting is the approver's standing word; only the approver sets it, and an `auto` entry is added or widened only with their words quoted in the commit message. `strict`, the default for an unlisted target, takes only cars whose `auth` names it.
- `maxCars`, `maxWaitMin`: departure thresholds; the project skill may override them.
- `skill`: the name of the project skill.

## Ledger

Kept where the Record seam says (one file per app, or an index per app and one file per train), with the train's `<code>`, each car (tickets, branch, head SHA, slip), the train's SHAs, the current stage, the deployed version per target, and the evidence of each car's acceptance.
