---
title: Develop
description: Validate skills, run the tests, edit the docs, and check a release before tagging.
---

The repository is the `pi-anchorloop` package: the workflow skills in `skills/` and the pi extensions in `pi/`.

## Checks

```bash
uv run python hooks/validate_all.py .   # skills, rules, and durable specs
uv run --with pytest pytest -q          # validators and the pi extensions (needs node)
```

Run both before declaring a change verified; `tests/test_pi_extension.py` loads the pi extension with Node.

## Docs

- `README.md` and `README.zh-TW.md` stay short: the pitch, the skill tree, install, quick start, and a one-line-per-extension table.
- This site is the reference. `site/` is a Starlight project served at https://wayne930242.github.io/anchorloop/ by `.github/workflows/pages.yml`.
- `docs/how-it-works.md` is the source of the extension reference; `site/scripts/sync.mjs` splits it by H2 into the pages under Extensions, so keep its headings stable.
- `docs/how-it-works.zh-TW.md` mirrors it line for line, and its first line names the English commit it matches.
- `cd site && npm ci && npm run check && npm run build` checks the twin, the hand-written pages' zh-TW twins, and every internal link and anchor.

<details>
<summary>Releasing</summary>

- Bump the version in `package.json` and `pyproject.toml` together whenever package capabilities, workflow contracts, or configurations change. Docs-only changes need no bump.
- Before pushing a `v*` tag, run both checks above in a clean detached worktree of the commit to tag (`git worktree add --detach <dir> <sha>`, removed afterwards): files a working tree holds outside git can let `validate_all.py` pass where the publish workflow fails.
- The `Publish` workflow runs both checks on the tag and publishes to npm unless that version is already there.

</details>
