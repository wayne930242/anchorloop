"""Validator for rule and instruction files (AGENTS.md, CLAUDE.md, rules/*.md, rules/*.rules)."""

from pathlib import Path

from .constants import DEFENSIVE_PATTERNS
from .utils import find_defensive_phrases


def check_rules_file(path: Path) -> list[str]:
    """Check rule files for direct expected behavior and anti-bloat."""
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"failed to read rule file: {e}"]

    # 1. Defensive phrasing detection
    found_patterns = find_defensive_phrases(text, DEFENSIVE_PATTERNS)
    if found_patterns:
        warnings.append(
            f"detected defensive wording: {', '.join(found_patterns)}"
        )

    # 2. Rule proliferation / bloat check
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if len(lines) > 200:
        warnings.append(
            f"rule file has {len(lines)} non-empty lines (over 200)"
        )

    # 3. Check for Simplified Chinese common distinctive characters
    # (Simple heuristic check for characters exclusively used in Simplified Chinese)
    simplified_chinese_chars = "为这就从时会过发对门书见长经说样开"
    found_sc = [c for c in simplified_chinese_chars if c in text]
    if found_sc:
        warnings.append(
            f"possible Simplified Chinese detected ({''.join(found_sc[:5])})"
        )

    return warnings
