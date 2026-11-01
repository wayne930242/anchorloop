#!/usr/bin/env python3
"""Validator entrypoint called by the pi extension in pi/validate-tool-use.ts.

Reads {"tool_input": {"file_path": ...}, "cwd": ...} on stdin, validates the
edited file against skill compactness, direct expected behavior, and durable
review standards, and prints {"additionalContext": ...} when it has advice.
"""

import json
import sys
from pathlib import Path

from validators.durable_validator import check_durable_spec
from validators.rule_validator import check_rules_file
from validators.skill_validator import check_skill_advisories, check_skill_md
from validators.utils import extract_file_path_from_payload


def run_validation(path: Path) -> list[str]:
    """Route file to appropriate validator based on path and filename."""
    warnings: list[str] = []
    name = path.name.lower()
    path_str = str(path).replace("\\", "/")

    # 1. SKILL.md
    if name == "skill.md":
        warnings.extend(check_skill_md(path))
        warnings.extend(check_skill_advisories(path))

    # 2. Rule and instruction files
    elif name in ("agents.md", "claude.md", "gemini.md") or "/rules/" in path_str:
        warnings.extend(check_rules_file(path))

    # 3. Durable spec artifacts
    elif "/docs/specs/" in path_str and name.endswith(".md"):
        warnings.extend(check_durable_spec(path))

    return warnings


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)
        data = json.loads(raw_input)
    except Exception:
        # Never block execution if input parsing fails
        sys.exit(0)

    try:
        file_path_str = extract_file_path_from_payload(data)
        if not file_path_str:
            print(json.dumps({}))
            sys.exit(0)

        cwd_str = data.get("cwd", "")
        cwd = Path(cwd_str) if cwd_str else Path.cwd()
        target_path = Path(file_path_str)
        if not target_path.is_absolute():
            target_path = cwd / target_path

        if not target_path.exists():
            print(json.dumps({}))
            sys.exit(0)

        warnings = run_validation(target_path)
        if warnings:
            try:
                rel = target_path.relative_to(cwd)
            except ValueError:
                rel = target_path

            lines = "\n".join(f"  - {w}" for w in warnings)
            msg = f"validator {rel}:\n{lines}"
            print(json.dumps({"additionalContext": msg}))
        else:
            print(json.dumps({}))

    except Exception as e:
        sys.stderr.write(f"anchorloop hook error: {e}\n")
        print(json.dumps({}))

    sys.exit(0)


if __name__ == "__main__":
    main()
