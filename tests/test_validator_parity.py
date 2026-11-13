"""The TypeScript validators in pi/support/validators.ts must give the same advice as the Python ones in hooks/."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node") or "node"
MODULE = REPO_ROOT / "pi" / "support" / "validators.ts"
HOOK_SCRIPT = REPO_ROOT / "hooks" / "validate_tool_use.py"

HARNESS = """
const [moduleUrl, cwd, ...files] = process.argv.slice(1);
const { validateFile } = await import(moduleUrl);
console.log(JSON.stringify(files.map((file) => validateFile(file, cwd) ?? null)));
"""

SKILL_OK = "---\nname: {name}\ndescription: Use when testing parity.\n---\n# Skill\n{body}\n"

FIXTURES: dict[str, str | bytes] = {
    "clean/AGENTS.md": "# Clean\n- Direct statement.\n",
    "defensive/AGENTS.md": "# Bad\n- You must never under any circumstances do X.\n- 千萬不要這樣\n",
    "defensive/CLAUDE.md": "- strict red line\n```\nnever under any circumstances\n```\n",
    "simplified/GEMINI.md": "这个为什么会发生\n",
    "bloated/rules/long.md": "\n".join(f"- rule {i}" for i in range(230)) + "\n",
    "crlf/AGENTS.md": b"# Bad\r\n- under no circumstances\r\n",
    "bom/AGENTS.md": b"\xef\xbb\xbf# Bad\n- zero tolerance for any slip\n",
    "badbytes/AGENTS.md": b"# Bad\n\xff\xfe\n",
    "skill-ok/SKILL.md": SKILL_OK.format(name="ok", body="Plain body."),
    "skill-frontmatter/SKILL.md": "# no frontmatter\n",
    "skill-extra/SKILL.md": "---\nname: x\nextra: 1\nauthor: me\ndescription: does things\n---\nbody\n",
    "skill-metadata/SKILL.md": "---\nname: m\ndescription: Use when m.\nmetadata:\n  merge-train-contract: \"1\"\n---\nbody\n",
    "skill-yaml/SKILL.md": "---\nname: x\ndescription: Use when a: b is true\n---\nbody\n",
    "skill-noname/SKILL.md": "---\ndescription: Use when x.\n---\nbody\n",
    "skill-emphasis/SKILL.md": SKILL_OK.format(
        name="e", body="NEVER edit the lockfile.\nMUST keep it because the reason is here.\nNEVER again.\nALWAYS go.\nNEVER mind."
    ),
    "skill-budget/SKILL.md": SKILL_OK.format(
        name="b", body="never do this. do not do that. avoid it. must not run. forbidden. 不要這樣。禁止那樣。"
    ),
    "skill-word-boundary/SKILL.md": SKILL_OK.format(name="w", body="Whenever, nevertheless, 不never_ avoided."),
    "skill-links/SKILL.md": SKILL_OK.format(name="l", body="See [a](a.md), [gone](gone.md), [web](https://x.io/y), `[c](code.md)`."),
    "skill-links/a.md": "See [deeper](sub/b.md) and [missing](nope.md#anchor).\n",
    "skill-links/sub/b.md": "leaf\n",
    "skill-orphan/SKILL.md": SKILL_OK.format(name="o", body="Nothing links the extra file."),
    "skill-orphan/extra.txt": "lonely\n",
    "skill-long/SKILL.md": SKILL_OK.format(name="long", body="\n".join(f"line {i}" for i in range(320))),
    "skill-long-refs/SKILL.md": SKILL_OK.format(name="long", body="\n".join(f"line {i}" for i in range(320))),
    "skill-long-refs/references/notes.md": "notes\n",
    "docs/specs/p/decision.md": "# Decision\nNothing here.\n",
    "docs/specs/p/requirements.md": "| Question | Answer | Basis | Status |\n| a | b | c | d |\nRule readiness.\n",
    "docs/specs/p/spec.md": "# Spec\nno status\n",
    "docs/specs/p/verification.md": "| Requirement | Evidence | Result |\n| a | b | pass |\n| c | d | maybe |\n| e | f | Pass |\nstrict red line\n",
    "docs/specs/p/other.md": "# Other\n",
    "docs/specs/q/decision.md": "| Question | Answer | Basis | Status |\n| a | b | c | d |\n",
    "docs/specs/q/spec.md": "Status: proposed\n",
    "skill-many-advisories/SKILL.md": SKILL_OK.format(name="m", body="".join(f"NEVER touch thing {n}.\n" for n in range(6))),
    "notes/readme.md": "# Plain\nnever under any circumstances\n",
}


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extension")
class TestValidatorParity(unittest.TestCase):
    @staticmethod
    def without_decoder_detail(advice: str | None) -> str | None:
        """The UTF-8 decoders word their errors differently; the rest of the advice must match."""
        return advice and advice.split("failed to read rule file:")[0] + ("failed to read rule file" if "failed to read" in advice else "")

    def test_typescript_matches_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in FIXTURES.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
            names = sorted(FIXTURES)

            proc = subprocess.run(
                [NODE, "--input-type=module", "-e", HARNESS, MODULE.as_uri(), str(root), *names],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            actual = json.loads(proc.stdout.strip().splitlines()[-1])

            for name, ts_advice in zip(names, actual, strict=True):
                payload = {"tool_name": "Edit", "tool_input": {"file_path": name}, "cwd": str(root)}
                py = subprocess.run(
                    [sys.executable, str(HOOK_SCRIPT)], input=json.dumps(payload), capture_output=True, text=True, check=True
                )
                py_advice = json.loads(py.stdout).get("additionalContext")
                with self.subTest(fixture=name):
                    self.assertEqual(self.without_decoder_detail(ts_advice), self.without_decoder_detail(py_advice))

    def test_missing_file_is_skipped(self):
        proc = subprocess.run(
            [NODE, "--input-type=module", "-e", HARNESS, MODULE.as_uri(), tempfile.gettempdir(), "no-such/AGENTS.md"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(proc.stdout), [None])


if __name__ == "__main__":
    unittest.main()
