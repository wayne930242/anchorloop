"""Unit tests for Durable artifacts and review validator."""

import tempfile
import unittest
from pathlib import Path

from hooks.validators.durable_validator import (
    check_decision_md,
    check_spec_md,
    check_verification_md,
)


class TestDurableValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_decision_md(self):
        f = self.base_path / "decision.md"
        f.write_text(
            """# Decision Artifact

Prerequisite skills and rules readiness verified.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Which storage engine? | SQLite | Embedded requirement | confirmed |
""",
            encoding="utf-8",
        )
        warnings = check_decision_md(f)
        self.assertEqual(warnings, [])

    def test_decision_md_needs_no_readiness_boilerplate(self):
        f = self.base_path / "decision.md"
        f.write_text("| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which storage engine? | SQLite | Embedded | confirmed |\n", encoding="utf-8")
        self.assertEqual(check_decision_md(f), [])

    def test_spec_md_needs_no_anchor_mention(self):
        f = self.base_path / "spec.md"
        f.write_text("# Specification\n\nStatus: proposed\n", encoding="utf-8")
        self.assertEqual(check_spec_md(f), [])

    def test_missing_decision_table(self):
        f = self.base_path / "decision.md"
        f.write_text("# Decision without table", encoding="utf-8")
        warnings = check_decision_md(f)
        self.assertTrue(any("Question | Answer | Basis | Status" in w for w in warnings))

    def test_valid_spec_md(self):
        f = self.base_path / "spec.md"
        f.write_text(
            """# Specification

Status: proposed

## Reality Anchor
Reality anchor: pytest test suite.
""",
            encoding="utf-8",
        )
        warnings = check_spec_md(f)
        self.assertEqual(warnings, [])

    def test_spec_missing_status(self):
        f = self.base_path / "spec.md"
        f.write_text(
            """# Specification without status
Reality anchor: pytest.
""",
            encoding="utf-8",
        )
        warnings = check_spec_md(f)
        self.assertTrue(any("must declare 'Status: proposed' or 'Status: approved'" in w for w in warnings))

    def test_valid_verification_md(self):
        f = self.base_path / "verification.md"
        f.write_text(
            """# Verification

| Requirement | Evidence | Result |
|---|---|---|
| Return code 0 | Ran `pytest tests/` output 5 passed | pass |

## Review
Tuned skill description for clearer triggers.
""",
            encoding="utf-8",
        )
        warnings = check_verification_md(f)
        self.assertEqual(warnings, [])

    def test_verification_invalid_result_state(self):
        f = self.base_path / "verification.md"
        f.write_text(
            """# Verification

| Requirement | Evidence | Result |
|---|---|---|
| Return code 0 | Ran `pytest` | success |
""",
            encoding="utf-8",
        )
        warnings = check_verification_md(f)
        self.assertTrue(any("invalid verification Result values" in w for w in warnings))

    def test_verification_review_defensive_phrasing(self):
        f = self.base_path / "verification.md"
        f.write_text(
            """# Verification

| Requirement | Evidence | Result |
|---|---|---|
| Return code 0 | Ran `pytest` | pass |

## Review
We added a rule that you must never under any circumstances allow broken links.
""",
            encoding="utf-8",
        )
        warnings = check_verification_md(f)
        self.assertTrue(any("detected defensive wording in verification/review" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
