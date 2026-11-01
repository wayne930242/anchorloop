"""Loads pi/validate-tool-use.ts with a stub pi API and checks the tool_result handler."""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTENSION = REPO_ROOT / "pi" / "validate-tool-use.ts"

HARNESS = """
const [extensionUrl, toolName, filePath, cwd] = process.argv.slice(1);
const { default: register } = await import(extensionUrl);
let handler;
register({ on: (event, fn) => { if (event === "tool_result") handler = fn; } });
const original = [{ type: "text", text: "ok" }];
const result = await handler(
  { toolName, input: { path: filePath }, content: original, isError: false },
  { cwd },
);
console.log(JSON.stringify(result ?? null));
"""


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extension")
class TestPiExtension(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_handler(self, tool_name: str, file_path: Path, env: dict | None = None):
        proc = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", HARNESS,
             EXTENSION.as_uri(), tool_name, str(file_path), str(self.base_path)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_write_appends_advice(self):
        test_file = self.base_path / "AGENTS.md"
        test_file.write_text("# Bad Rules\n- You must never under any circumstances do X.\n", encoding="utf-8")
        result = self.run_handler("write", test_file)
        self.assertEqual(result["content"][0], {"type": "text", "text": "ok"})
        self.assertEqual(len(result["content"]), 2)
        self.assertTrue(result["content"][1]["text"].startswith("validator AGENTS.md:\n"), result["content"][1]["text"])
        self.assertIn("defensive wording", result["content"][1]["text"])

    def test_clean_file_leaves_result_unchanged(self):
        test_file = self.base_path / "AGENTS.md"
        test_file.write_text("# Clean Rules\n- Direct statement.\n", encoding="utf-8")
        self.assertIsNone(self.run_handler("edit", test_file))

    def machine_without_python(self, with_store_stub: bool) -> dict:
        """An environment whose PATH holds node and, optionally, the Windows Store python3 stub that exits non-zero."""
        bin_dir = self.base_path / "bin"
        bin_dir.mkdir()
        os.symlink(shutil.which("node"), bin_dir / "node")
        if with_store_stub:
            stub = bin_dir / "python3"
            stub.write_text("#!/bin/sh\necho 'Python was not found; run without arguments to install from the Microsoft Store' >&2\nexit 9009\n")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return {**os.environ, "PATH": str(bin_dir)}

    def test_validation_runs_without_python_on_path(self):
        env = self.machine_without_python(with_store_stub=False)
        bad = self.base_path / "AGENTS.md"
        bad.write_text("# Bad Rules\n- You must never under any circumstances do X.\n", encoding="utf-8")
        result = self.run_handler("write", bad, env)
        self.assertEqual(len(result["content"]), 2)
        self.assertIn("defensive wording", result["content"][1]["text"])
        self.assertNotIn("did not run", result["content"][1]["text"])

    def test_windows_store_python_stub_adds_no_notice(self):
        env = self.machine_without_python(with_store_stub=True)
        clean = self.base_path / "AGENTS.md"
        clean.write_text("# Clean Rules\n- Direct statement.\n", encoding="utf-8")
        self.assertIsNone(self.run_handler("edit", clean, env))

    def test_crlf_files_validate_like_lf_files(self):
        bad = self.base_path / "AGENTS.md"
        bad.write_bytes(b"# Bad Rules\r\n- You must never under any circumstances do X.\r\n")
        self.assertIn("defensive wording", self.run_handler("write", bad)["content"][1]["text"])

    def test_other_tools_are_ignored(self):
        test_file = self.base_path / "AGENTS.md"
        test_file.write_text("# Bad Rules\n- You must never under any circumstances do X.\n", encoding="utf-8")
        self.assertIsNone(self.run_handler("read", test_file))


if __name__ == "__main__":
    unittest.main()
