# Author a skill

**You own the skill's behavior change, and nothing beyond it.**

1. Name the layer: knowledge (what the model lacks), prohibition (a habit to block), process (an order), taste (an aesthetic), or discipline (shortcuts and false claims). The layer sets the length, the tone, and how much the description must carry.
2. For a new skill or playbook, have the model attempt the task without it and record where it fails; the first version covers those failures and nothing more.
3. A new skill starts from [the template](../references/template-skill.md); a new playbook copies an existing one's shape (ownership line, steps, `Reply:`).
4. Apply the **Craft Levers**, then **Hold the Size**.
5. For a change that answers a recorded failure, rerun the smallest slice of that task that exercised the edited instruction, in a fresh-context worker with the edited skill, in a clean directory or disposable worktree, with outward-facing steps (push, deploy, tickets, chat) out of scope in the brief; when no safe slice exists, record `rerun: n/a — <reason>` and rest on the validator and the no-op test. Phrase it as ordinary work with no mention of testing, and judge from the files the worker read and the shape of its output, not its claims, because a worker told it is tested reads more carefully than a real run does. The recorded failure must not recur. To compare variants, give each the same organic prompt in a clean directory and read the tool-call transcripts yourself.
6. Fix a broken skill met mid-task in its own change, not tangled into the task's diff.

**Reply:** the files changed with the net line count of each, the layer, the bare-run failures the change covers, and the rerun's before and after.
