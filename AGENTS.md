# Agent Working Agreements: anchorloop

This repository is the `pi-anchorloop` package: the workflow skills in `skills/` and the pi extensions in `pi/`, which the README's Extensions table describes.

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
