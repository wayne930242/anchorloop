# Agent Working Agreements: anchorloop

This repository is the `pi-anchorloop` package: the workflow skills in `skills/` and the pi extensions in `pi/`, which the documentation site's Extensions reference describes.

## Core Directives

- All prompts, agent instructions, and code comments must be in English.
- User communication must always be in Traditional Chinese (繁體中文).
- Prompts, documentation, and guidelines state expected behavior directly, without defensive phrasing or prohibitive lists.
- Work runs through an entry skill over the loop in `skills/anchorloop/SKILL.md`; `pi/anchor-gate.ts` warns when an edit runs before a Reality anchor is stated.
- Commit messages must not mention AI tools.

- `pi/book.ts` adds no new recognition of anchor command forms until the 2026-11-18 review of how many real failures the book caught; unrecognized forms go through `anchorloop_stage verify`.

## Versioning & Release Directives

- Bump the version in `package.json` and `pyproject.toml` together whenever package capabilities, workflow contracts, or configurations change.
- Before pushing a `v*` tag, run both checks under Development Workflow in a clean detached worktree of the commit to tag (`git worktree add --detach <dir> <sha>`, removed afterwards): files a working tree holds outside git can let `validate_all.py` pass where the publish workflow fails, as v2.15.0 did.

## Development Workflow

- Run `uv run python hooks/validate_all.py .` to ensure skills and rules conform to the compactness and quality baselines.
- Run `uv run --with pytest pytest -q` before declaring verification complete; `tests/test_pi_extension.py` loads the pi extension with Node.

## Docs

- `README.md` and `README.zh-TW.md` stay short: the pitch, the skill tree, install, quick start, and one line per extension. Behavior reference goes on the site; a user-facing feature gets its guide page in both languages.
- `site/` is the Starlight documentation site, served at https://wayne930242.github.io/anchorloop/ by `.github/workflows/pages.yml`. `site/scripts/sync.mjs` generates the Extensions pages from `docs/how-it-works.md` split by H2, so `docs/` stays the one source for long behavior text; keep its headings stable, since pages and the README link to them. `cd site && npm ci && npm run check && npm run build` checks the twin and every internal link and anchor.
- `docs/how-it-works.zh-TW.md` mirrors `docs/how-it-works.md` line for line, and its first line names the English commit it matches. A change to the English file changes the same lines of the twin and moves that commit; `npm --prefix site run check` fails when the headings, line kinds, or backticked tokens no longer match and lists the English commits not yet translated. Each hand-written page under `site/src/content/docs/` has a twin under `zh-tw/` with the same headings, folds, diagrams, and tables, which the same check enforces.
- Each Mermaid diagram carries a comment naming the source file it was checked against; a change to that code rechecks the diagram.
