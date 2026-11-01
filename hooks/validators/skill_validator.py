"""Validator for SKILL.md files focusing on compactness and direct expected behavior."""

import re
from collections import Counter
from pathlib import Path

from .constants import (
    DEFENSIVE_PATTERNS,
    MAX_ADVISORIES,
    EMPHATIC_WORDS,
    REASON_WORDS,
    RED_LINE_DENSITY,
    RED_LINE_MARKERS,
    RED_LINE_MIN_BUDGET,
    SKILL_ALLOWED_FIELDS,
    SKILL_MAX_RECOMMENDED_LINES,
)
from .utils import (
    extract_markdown_links,
    find_defensive_phrases,
    parse_frontmatter,
    strip_code,
)


def check_skill_md(path: Path) -> list[str]:
    """Run streamlining and standardization checks on a SKILL.md file."""
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"failed to read SKILL.md: {e}"]

    skill_dir = path.parent
    lines = text.splitlines()

    # 1. Frontmatter check
    fields = parse_frontmatter(text)
    if fields is None:
        warnings.append("missing or invalid YAML frontmatter (--- ... ---)")
    else:
        extra_fields = sorted(set(fields.keys()) - SKILL_ALLOWED_FIELDS)
        if extra_fields:
            warnings.append(f"extra frontmatter fields: {', '.join(extra_fields)}")

        if "name" not in fields or not fields["name"].strip():
            warnings.append("missing required frontmatter field: 'name'")

        # The regex parser accepts what pi's YAML parser rejects, and pi then skips the whole skill.
        for key in ("name", "description"):
            raw = next((line.split(":", 1)[1].strip() for line in lines[1:] if line.startswith(f"{key}:")), "")
            if raw and raw[0] not in "\"'|>" and (": " in raw or " #" in raw):
                warnings.append(f"quote the {key}: YAML reads an unquoted ': ' or ' #' as syntax, and pi skips the skill")

        if "description" not in fields or not fields["description"].strip():
            warnings.append("missing required frontmatter field: 'description'")
        else:
            desc = fields["description"]
            if "use when" not in desc.lower():
                warnings.append("description should specify trigger criteria (include 'Use when...')")

    # 2. Compactness check (streamlined skills)
    if len(lines) > SKILL_MAX_RECOMMENDED_LINES:
        has_references = (skill_dir / "references").is_dir()
        if not has_references:
            warnings.append(
                f"skill has {len(lines)} lines (over {SKILL_MAX_RECOMMENDED_LINES}) and no references/"
            )

    # 3. Broken markdown links, followed through every Markdown file SKILL.md reaches
    root = skill_dir.resolve()
    reached: dict[Path, str] = {path.resolve(): text}
    linked: set[Path] = set()
    pending = [path.resolve()]
    while pending:
        source = pending.pop()
        for link in extract_markdown_links(reached[source]):
            target = (source.parent / link).resolve()
            if not target.exists():
                where = "" if source == path.resolve() else f" (in {source.relative_to(root).as_posix()})"
                warnings.append(f"broken local link: {link}{where}")
                continue
            linked.add(target)
            if target.suffix == ".md" and target.is_relative_to(root) and target not in reached:
                reached[target] = target.read_text(encoding="utf-8")
                pending.append(target)

    # 4. Orphaned files check
    corpus = "\n".join(reached.values())
    for f in skill_dir.rglob("*"):
        if f == path or f.is_dir():
            continue
        rel = f.relative_to(skill_dir).as_posix()
        if not (f.resolve() in linked or rel in corpus or f.name in corpus):
            warnings.append(f"orphaned file not referenced in SKILL.md: {rel}")

    # 5. Defensive phrasing check
    found_patterns = find_defensive_phrases(text, DEFENSIVE_PATTERNS)
    if found_patterns:
        warnings.append(
            f"detected defensive anti-pattern(s): {', '.join(found_patterns)}"
        )

    return warnings


def check_skill_advisories(path: Path) -> list[str]:
    """Red-line advisories for the author; they never count as validation failures."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    body = strip_code(text)
    lines = body.splitlines()
    advisories: list[str] = []

    # 1. Budget: red lines are earned by an observed failure, so their count stays small.
    markers = len(re.findall(RED_LINE_MARKERS, body, re.IGNORECASE))
    budget = max(RED_LINE_MIN_BUDGET, int(sum(1 for line in lines if line.strip()) * RED_LINE_DENSITY))
    if markers > budget:
        advisories.append(f"{markers} red-line markers exceed the budget of {budget}")

    # 2. Reasoned: an emphatic word carries its reason on the same or next line.
    # 3. Once: an emphatic word is spent a single time.
    seen: Counter[str] = Counter()
    for number, line in enumerate(lines, start=1):
        for word in re.findall(EMPHATIC_WORDS, line):
            seen[word] += 1
            window = " ".join(lines[number - 1 : number + 1])
            if not re.search(REASON_WORDS, window, re.IGNORECASE):
                advisories.append(f"line {number}: emphatic '{word}' has no reason beside it")
    for word, count in seen.items():
        if count > 1:
            advisories.append(f"emphatic '{word}' appears {count} times")

    return advisories[:MAX_ADVISORIES]
