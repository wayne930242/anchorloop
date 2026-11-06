# Decision: integrating and deploying entry skills

## Outcome and actors

The generic merge-train, assembly, and deploy procedure leaves the host that first carried it (`pi-straw-boss` `prompts/integrator.md`) and becomes two anchorloop entry skills, `integrating` and `deploying`. A host fills a few named seams through its own session instructions; anchorloop names the seams and nothing about any host.

## Scope

In: the two entry skills with their playbooks and the shared seam reference, the entry index and README entries, the version bump to 2.10.0, and the mapping from the source material to the new homes.

Out: edits to `pi-straw-boss` or `weihung-basic-agent` (the host-side follow-up is listed in `design.md`), a release, publish, or tag, and any extension code.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| How many skills | Two: `integrating` (merge stage) and `deploying` (deploy stage, UAT stage, deployment rules) | boss 2026-11-06 「兩個 skill：integrating + deploying」 | confirmed |
| Where the deployment rules go | Into `deploying`; the rules file shrinks to one line pointing at it | boss 2026-11-06 「併入 deploying，規則檔改成一行指向它」 | confirmed |
| Interface to hosts | anchorloop names only generic seams and never mentions the host; a host's session prompt binds the seams; an unbound seam has a default | boss 2026-11-06 「sb's session prompt binds the seams」 | confirmed |
| Project skill headings | Kept exactly: `Light checks`, `Train assembly`, `Full gates`, `Merge`, `Post-merge`, `Deploy`, `Deploy verify`, `UAT`, `Urgent lane`, `Load`, no heading changes; the project skill gains one pointer line | task brief | confirmed |
| Seam set | Six: handoff route, batch owner, approval, record, escalation route, settings | `integrator.md` couples to a relay (slip, answers, blocked, idle, clash announcement), a named owner, a quoted authorization, a ledger path, and the app config; each is one seam | grounded |
| Default for every seam | The session is coordinator, owner, and record keeper; it asks the user before any merge to a shared branch or any deploy | boss 2026-11-06 and task brief | confirmed |
| Default ledger location | `scratch/trains/<app>.json` under the git root | the decision trail already keeps run state in `scratch/`, which the anchor gate and the repository treat as machine-local | grounded |
| Where the UAT stage lives | In `deploying`, as a section that runs `human-feedback`'s uat playbook with the train additions | the stage follows `Deploy verify` and judges the deployed result; the playbook owns capture, page, and cleanup | grounded |
| Vocabulary | `train` and `car` stay; a "batch owner" is the role | the heading `Train assembly` and the slip's `car:` line are fixed by the contract | grounded |
| Version | 2.10.0 in `package.json`, `pyproject.toml`, `uv.lock` | `AGENTS.md`: new capabilities bump the minor version | confirmed |
