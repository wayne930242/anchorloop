# Seams

`integrating` and `deploying` run the same procedure under any host. They leave six places open, called seams, where a host or a project decides who, where, or how. Each seam below says what its mechanism must do; an unbound seam takes its default.

## Binding

The session's instructions or the project's instructions hold at most one block. Each line binds one seam to a mechanism; a seam the block leaves out keeps its default:

    ## Seam bindings
    - Handoff route: <how a car slip reaches the batch owner and how its answers come back>
    - Batch owner: <who assembles, gates, and merges a batch, and how it is named and closed>
    - Approval: <who authorizes a merge and each deploy target, and how their words reach the slip>
    - Record: <where the ledger lives>
    - Escalation route: <where blocked, idle, and deploy announcements go>
    - Settings: <where the integration branch, stages, targets, and thresholds come from>

Read the block before the first step. A binding whose mechanism the session cannot reach is a blocker: report it through the Escalation route and keep the stage closed, because the default would silently move a decision to a party the host did not choose.

## Terms

- **Car**: one reviewed branch offered to the integration branch, with its slip.
- **Train**: the cars assembled, gated, merged, and shipped together, identified by a `<code>` (date and letter, such as `2026-11-05-a`).
- **Integration branch**: the shared branch a train merges into (`base`).
- **Coordinator**: the party that answers for a car and receives the answers about it.
- **Project skill**: the project's skill that holds the heading contract in [integrating](../SKILL.md).

## The seams

| Seam | Decides | Default when unbound |
|---|---|---|
| Handoff route | How a car slip reaches the batch owner; how the train number, a returned car, and the landed notice reach the coordinator. | The session is its own coordinator and batch owner: it writes each slip into the ledger and answers itself. It awaits no other coordinator. |
| Batch owner | Who receives cars, assembles, gates, merges, and deploys, and how the owner is named and closed. | The session itself, in a worktree `train-<code>` beside the repository. It closes when its ledger holds no open train. |
| Approval | Who authorizes a merge to the integration branch and each deploy target, and how the words reach the slip's `auth`. | The user. The session asks one question round naming the integration branch and every deploy target the cars list, and quotes the reply in `auth`. Every target is `strict`. |
| Record | Where the ledger lives. | `scratch/trains/<app>.json` under the git root. It is machine-local state: stage files by name and keep it out of commits. |
| Escalation route | Where `blocked`, `idle`, and the announcement of a deploy the owner starts itself go. | The session says it in its reply to the user. No announcement is needed because no other session shares the targets. |
| Settings | The integration branch, the stages, the targets, `maxCars`, `maxWaitMin`, and the project skill's name. | The project's instructions name them. Left unnamed: `base` is the remote's default branch, `stages` is `merge`, no target is listed, `maxCars` is 4, `maxWaitMin` is 60, and a missing project skill is a `blocked`. |

## Settings keys

- `base`: the integration branch.
- `stages`: ordered; `merge` is first and always present, then optionally `deploy`, then `uat` (only after `deploy`).
- `targets`: each deploy target to `auto` or `strict`. `auto` takes every train with no per-car approval, since the setting is the approver's standing word; only the approver sets it, and an `auto` entry is added or widened only with their words quoted in the commit message. `strict`, the default for an unlisted target, takes only cars whose `auth` names it.
- `maxCars`, `maxWaitMin`: departure thresholds; the project skill may override them.
- `skill`: the name of the project skill.

## Ledger

One file per app with the train's `<code>`, each car (tickets, branch, head SHA, slip), the train's SHAs, the current stage, the deployed version per target, and each UAT verdict. The batch owner keeps one `todo` per train.
