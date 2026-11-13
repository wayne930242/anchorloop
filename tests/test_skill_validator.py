"""Unit tests for SKILL.md validator."""

import tempfile
import unittest
from pathlib import Path

from hooks.validators.skill_validator import check_skill_advisories, check_skill_md


class TestSkillValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_streamlined_skill(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
---

# My Skill

Direct instructions for execution.
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertEqual(warnings, [])

    def test_unquoted_value_that_yaml_rejects(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        for value, broken in (("Use when editing code: tests too.", True), ("Use when editing code #1.", True),
                              ('"Use when editing code: tests too."', False), ("Use when editing code, tests too.", False)):
            with self.subTest(value=value):
                skill_file.write_text(f"---\nname: my-skill\ndescription: {value}\n---\n\n# My Skill\n", encoding="utf-8")
                warnings = check_skill_md(skill_file)
                self.assertEqual(any("quote the description" in w for w in warnings), broken, warnings)

    def test_missing_frontmatter(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# My Skill without frontmatter", encoding="utf-8")

        warnings = check_skill_md(skill_file)
        self.assertTrue(any("missing or invalid YAML frontmatter" in w for w in warnings))

    def test_extra_frontmatter_fields(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
author: John Doe
version: 1.0.0
---
# Content
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertTrue(any("extra frontmatter fields" in w for w in warnings))

    def test_metadata_frontmatter_field_allowed(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
metadata:
  merge-train-contract: "1"
---
# Content
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertFalse(any("extra frontmatter fields" in w for w in warnings), warnings)

    def test_broken_markdown_links(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
---
See [Missing Ref](references/missing.md).
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertTrue(any("broken local link: references/missing.md" in w for w in warnings))

    def test_orphaned_files(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        ref_dir = skill_dir / "references"
        ref_dir.mkdir()
        orphan = ref_dir / "orphan.md"
        orphan.write_text("# Orphan content", encoding="utf-8")

        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
---
# Skill without linking orphan
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertTrue(any("orphaned file not referenced" in w for w in warnings))

    def test_links_inside_linked_files(self):
        skill_dir = self.base_path / "my-skill"
        (skill_dir / "playbooks").mkdir(parents=True)
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "shape.md").write_text("# Shape", encoding="utf-8")
        (skill_dir / "playbooks" / "fix.md").write_text(
            "See [shape](../references/shape.md) and [gone](missing.md).", encoding="utf-8"
        )
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
---
- [fix](playbooks/fix.md)
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertIn("broken local link: missing.md (in playbooks/fix.md)", warnings)
        self.assertFalse(any("orphaned" in w for w in warnings), warnings)

    def test_defensive_anti_pattern_detection(self):
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: Use when executing streamlined tasks.
---
You must never under any circumstances modify code without permission.
""",
            encoding="utf-8",
        )
        warnings = check_skill_md(skill_file)
        self.assertTrue(any("detected defensive anti-pattern" in w for w in warnings))

    def write_skill(self, body: str) -> Path:
        skill_dir = self.base_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            f"---\nname: my-skill\ndescription: Use when executing streamlined tasks.\n---\n{body}",
            encoding="utf-8",
        )
        return skill_file

    def test_red_lines_within_budget_have_no_advisory(self):
        skill_file = self.write_skill("Do not skip the check because the build trusts it.\nNever reuse a stale token.\n")
        self.assertEqual(check_skill_advisories(skill_file), [])

    def test_red_line_budget_exceeded(self):
        skill_file = self.write_skill("".join(f"Do not do thing {n}.\n" for n in range(6)))
        advisories = check_skill_advisories(skill_file)
        self.assertTrue(any("exceed the budget" in a for a in advisories))

    def test_emphatic_word_needs_a_reason(self):
        skill_file = self.write_skill("NEVER edit the lockfile.\n")
        advisories = check_skill_advisories(skill_file)
        self.assertTrue(any("line 5" in a and "no reason" in a for a in advisories))

    def test_emphatic_word_with_reason_on_next_line_passes(self):
        skill_file = self.write_skill("NEVER edit the lockfile.\nIt is generated, because edits are overwritten.\n")
        self.assertEqual(check_skill_advisories(skill_file), [])

    def test_emphatic_word_spent_once(self):
        skill_file = self.write_skill("MUST run tests because releases ship from here.\nMUST bump the version because installs pin it.\n")
        advisories = check_skill_advisories(skill_file)
        self.assertTrue(any("'MUST' appears 2 times" in a for a in advisories))

    def test_advisories_are_capped_at_three_per_edit(self):
        skill_file = self.write_skill("".join(f"NEVER touch thing {n}.\n" for n in range(6)))
        advisories = check_skill_advisories(skill_file)
        self.assertEqual(len(advisories), 3)

    def test_advisories_carry_no_style_lesson(self):
        skill_file = self.write_skill("".join(f"Do not do thing {n}.\n" for n in range(6)) + "NEVER edit the lockfile.\n")
        for advisory in check_skill_advisories(skill_file):
            self.assertNotIn(". ", advisory)

    def test_code_blocks_are_ignored(self):
        skill_file = self.write_skill("```text\nNEVER NEVER NEVER do not do not do not do not\n```\n")
        self.assertEqual(check_skill_advisories(skill_file), [])

    def test_advisories_do_not_fail_validation(self):
        skill_file = self.write_skill("NEVER edit the lockfile.\n")
        self.assertEqual(check_skill_md(skill_file), [])


if __name__ == "__main__":
    unittest.main()
