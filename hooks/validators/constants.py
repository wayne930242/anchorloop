"""Constants for skill, rule, and durable spec validation."""

# Allowed fields in SKILL.md YAML frontmatter
SKILL_ALLOWED_FIELDS = frozenset({"name", "description", "metadata"})

# Maximum recommended lines for a self-contained SKILL.md before progressive disclosure (official standard: 300 lines)
SKILL_MAX_RECOMMENDED_LINES = 300

# Defensive phrasing patterns to discourage (encourage stating expected behavior directly)
DEFENSIVE_PATTERNS = [
    r"never under any circumstances",
    r"under no circumstances",
    r"you must never ever",
    r"do not under any condition",
    r"strict red line",
    r"absolute red line",
    r"prohibited at all costs",
    r"zero tolerance for any",
    r"absolutely forbidden to ever",
    r"無限多的紅線",
    r"千萬不要",
    r"嚴禁在任何情況下",
    r"絕對不可",
]

# Red-line advisories: markers are counted against a budget of max(MIN_BUDGET, lines * DENSITY).
# Existing skills peak at 0.067 markers per line, so the budget fires only on clear inflation.
RED_LINE_MARKERS = (
    r"\b(never|must not|do not|don't|forbidden|barred|prohibited|avoid)\b"
    r"|不要|禁止|不得|不准|嚴禁"
)
MAX_ADVISORIES = 3
RED_LINE_MIN_BUDGET = 3
RED_LINE_DENSITY = 0.10
# Emphatic capitals are matched case-sensitively and need a reason on the same or next line.
EMPHATIC_WORDS = r"\b(NEVER|ALWAYS|MUST NOT|MUST|FORBIDDEN|DO NOT)\b"
REASON_WORDS = r"\b(because|otherwise|so that|since)\b|否則|因為|以免"

# Essential core rules to check during durable pre-flight
CORE_RULES = [
    "Traditional Chinese communication",
    "English instructions and prompts",
    "Direct statement of expected behavior without defensive phrasing",
    "Anchorloop reality anchor named before first production edit",
]

# Standard verification result states
VALID_VERIFICATION_RESULTS = {"pass", "fail", "unknown"}
