# Verification: integrating and deploying

| Requirement | Evidence | Result |
|---|---|---|
| Skills, rules, and durable specs conform to the validators | `uv run python hooks/validate_all.py .` printed "All skills, rules, and durable specs passed validation cleanly." | pass |
| Package tests pass, including version sync and skill coverage | `uv run --with pytest pytest -q`: 350 passed | pass |
| Versions agree at 2.10.0 | `package.json`, `pyproject.toml`, `uv.lock` all 2.10.0; `tests/test_manifests.py` passed | pass |
| Each `SKILL.md` stays under 300 lines | `skills/integrating/SKILL.md` 61 lines, `skills/deploying/SKILL.md` 40 lines | pass |
| The ten project-skill headings appear exactly as in the source contract | A script compared the `apps-config.md` heading column with `skills/integrating/**` and `skills/deploying/**`: none missing | pass |
| Nothing from `integrator.md`'s procedure is lost | Every row of the source mapping in `design.md` has a home; a token sweep of 60 phrases from `integrator.md` over the new files found only `show_doc` and `blank box`, which the `human-feedback` uat playbook (step 4) owns and the UAT stage links | pass |
| The skills name no host | A grep of the new skills for the host's name, its tools, and its relay vocabulary found nothing | pass |
| The deployment rules' four items are in `deploying` | `skills/deploying/SKILL.md` Rules 1 to 4 against `weihung-basic-agent/rules/deployment.md` | pass |
| A fresh-context agent running the new skills reproduces the source behavior | Not run: the brief excludes a reviewer and no recorded failure exists to replay; the read above was the author's own, not independent. `rerun: n/a — new skills, no recorded failure` | unknown |
| A host can bind the seams from its own session prompt | Binding block specified in `spec.md` and `seams.md`; no host consumed it yet | unknown |
