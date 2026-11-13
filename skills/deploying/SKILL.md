---
name: deploying
description: Use when shipping a build to a target such as a test environment, staging, production, a server, or a cluster, when running the deploy stage of a merge train, syncing files to a host (rsync, Ansible), rolling back a failed deploy, or checking that a target runs the version just shipped.
metadata:
  merge-train-contract: "1"
---

# Deploying

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is that each target runs the version that was shipped, read from the target as the project skill's `Deploy verify` shows it, after the tests ran, with each target's approval quoted (or the target marked `auto`).

A deploy ships every car in the train at once, and a target someone depends on takes the change at once. Order, approval, and verification are per target, because one target's success says nothing about the next.

## Seams

All seven seams of [seams](../integrating/references/seams.md) apply with the same defaults and bindings. Each command of deploy, verify, and rollback runs through the Step runner; the owner of a train orders its targets per `Deploy`. A train-less deploy (one change, the session as its own owner) follows the same steps, and the reply carries what the ledger would.

## Rules

- Before an `rsync --delete`, list the runtime files the target holds (`.token-override`, state files, `.env`) and confirm each is excluded, because a delete-sync removes whatever the source does not carry and those files exist only on the target.
- Run the project's test suite before any deploy, because an untested deploy ships unknown behavior to a target in use. Inside a train, `Full gates` on the merged head is that run.
- Run Ansible playbooks with `--check` first on production targets and read the planned changes before the real run; any other tool with a dry run takes the same step on a live target.
- Before a destructive sync, verify the target directory exists and is non-empty, because an empty or missing target is usually a wrong or unmounted path.

## Where the commands come from

The project skill's `## Deploy` and `## Deploy verify` hold them (heading contract in [integrating](../integrating/SKILL.md)). With no project skill, the project's instructions do; with neither, ask the approver for the target's procedure before the first step, because a guessed deploy command is the one that cannot be undone.

## Playbooks

- [deploy](playbooks/deploy.md): per-target order, approval, serialization, dry run, deploy, verify.
- [rollback](playbooks/rollback.md): a failed target, a failed verify, or a revert after landing.
