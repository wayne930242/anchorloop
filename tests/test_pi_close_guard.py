"""Loads pi/close-guard.ts with a stub pi API and replays a session branch against its settle handler."""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

EXTENSION = Path(__file__).resolve().parent.parent / "pi" / "close-guard.ts"

HARNESS = """
const [extensionUrl, branchJson, entriesJson] = process.argv.slice(1);
const handlers = {};
const tools = [];
const pi = { on: (event, fn) => { (handlers[event] ??= []).push(fn); }, registerTool: (tool) => tools.push(tool.name) };
const { default: register } = await import(extensionUrl);
register(pi);
const branch = JSON.parse(branchJson);
const ctx = { cwd: process.cwd(), sessionManager: { getBranch: () => branch } };
const event = { outcome: "completed", entries: JSON.parse(entriesJson), continue: false };
let result = null;
for (const fn of handlers.agent_before_settle ?? []) result = (await fn(event, ctx)) ?? result;
console.log(JSON.stringify({ result, tools, events: Object.keys(handlers) }));
"""


def say(text: str) -> dict:
    return {"type": "message", "id": f"a{abs(hash(text)) % 10**8}", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def call(name: str, call_id: str, **arguments) -> dict:
    return {"type": "message", "id": f"c-{call_id}", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": call_id, "name": name, "arguments": arguments}]}}


def result(name: str, call_id: str, is_error: bool = False, text: str = "ok") -> dict:
    return {"type": "message", "id": f"r-{call_id}", "message": {"role": "toolResult", "toolCallId": call_id, "toolName": name,
                                                              "content": [{"type": "text", "text": text}], "isError": is_error}}


def edit(call_id: str, path: str = "src/app.py") -> list[dict]:
    return [call("edit", call_id, path=path), result("edit", call_id)]


def bash(call_id: str, command: str, ok: bool = True) -> list[dict]:
    return [call("bash", call_id, command=command), result("bash", call_id, is_error=not ok, text="" if ok else "Command exited with code 1")]


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extension")
class TestCloseGuard(unittest.TestCase):
    def settle(self, branch: list[dict], entries: list[dict] | None = None) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", HARNESS, EXTENSION.as_uri(), json.dumps(branch), json.dumps(entries or [])],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def notice(self, branch: list[dict]) -> str | None:
        out = self.settle(branch)["result"]
        if not out:
            return None
        self.assertNotIn("continue", out, "the guard never forces a turn")
        added = out["entries"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["type"], "custom_message")
        self.assertEqual(added[0]["customType"], "anchorloop-close-guard")
        text = added[0]["content"]
        self.assertNotIn("\n", text, "the notice is a single line")
        self.assertLessEqual(len(text), 200)
        return text

    def test_it_registers_no_tool_and_listens_at_settle(self):
        out = self.settle([])
        self.assertEqual(out["tools"], [])
        self.assertIn("agent_before_settle", out["events"])

    def test_no_change_means_no_notice(self):
        branch = [say("Anchor: `pytest -q`"), *bash("b1", "git status"), call("read", "r1", path="a.py"), result("read", "r1")]
        self.assertIsNone(self.notice(branch))

    def test_an_edit_without_an_anchor_line_is_named(self):
        notice = self.notice([say("Fixing it."), *edit("e1")])
        self.assertIn("Anchor:", notice)

    def test_a_passing_anchor_run_after_the_last_edit_is_quiet(self):
        branch = [say("Plan.\nAnchor: `pytest -q tests/test_app.py`"), *edit("e1"), *bash("b1", "uv run  pytest -q tests/test_app.py")]
        self.assertIsNone(self.notice(branch))

    def test_an_edit_after_the_passing_run_is_named(self):
        branch = [say("Anchor: `pytest -q`"), *edit("e1"), *bash("b1", "pytest -q"), *edit("e2", "src/other.py")]
        notice = self.notice(branch)
        self.assertIn("`pytest -q`", notice)

    def test_a_failing_last_run_is_named(self):
        branch = [say("Anchor: `pytest -q`"), *edit("e1"), *bash("b1", "pytest -q", ok=False)]
        self.assertIn("`pytest -q`", self.notice(branch))

    def test_every_backticked_check_must_pass(self):
        branch = [say("**Anchor:** `npm test` and `npm run lint`"), *edit("e1"), *bash("b1", "npm test")]
        notice = self.notice(branch)
        self.assertIn("`npm run lint`", notice)
        self.assertNotIn("`npm test`", notice)

    def test_a_later_anchor_line_replaces_the_earlier_one(self):
        branch = [say("Anchor: `pytest -q`"), *edit("e1"), say("Anchor: `make check`"), *bash("b1", "make check")]
        self.assertIsNone(self.notice(branch))

    def test_an_anchor_without_a_command_is_not_judged(self):
        branch = [say("Anchor: the reviewer's verdict on the diff"), *edit("e1")]
        self.assertIsNone(self.notice(branch))

    def test_a_todo_metadata_anchor_counts(self):
        branch = [call("todo", "t1", action="create", subject="fix", metadata={"anchor": "go test ./..."}), result("todo", "t1"),
                  *edit("e1"), *bash("b1", "cd svc && go test ./...")]
        self.assertIsNone(self.notice(branch))
        self.assertIn("`go test ./...`", self.notice([*branch, *edit("e2")]))

    def test_ledger_anchor_requires_a_real_run(self):
        for args in ({"anchor": "make check"}, {"tasks": [{"anchor": "old"}, {"anchor": "make check"}, {"anchor": " "}]},
                     {"tasks": [{"anchor": "old"}, {"metadata": {"anchor": "make check"}}]}):
            with self.subTest(args=args):
                branch = [call("todo", "t", action="create", **args), *edit("e")]
                self.assertIn("`make check`", self.notice(branch))
                self.assertIsNone(self.notice([*branch, *bash("b", "make check")]))

    def test_a_failed_edit_is_not_a_change(self):
        branch = [say("Anchor: `pytest -q`"), *bash("b1", "pytest -q"), call("edit", "e1", path="a.py"), result("edit", "e1", is_error=True)]
        self.assertIsNone(self.notice(branch))

    def test_the_notice_is_not_repeated_for_the_same_change(self):
        branch = [say("Anchor: `pytest -q`"), *edit("e1")]
        first = self.settle(branch)["result"]["entries"][0]
        self.assertIsNone(self.notice([*branch, {"type": "custom_message", **first}]))
        self.assertIsNotNone(self.notice([*branch, {"type": "custom_message", **first}, *edit("e2")]))

    def test_earlier_proposed_entries_are_kept(self):
        prior = {"type": "custom", "customType": "other", "data": {}}
        out = self.settle([say("Anchor: `pytest -q`"), *edit("e1")], entries=[prior])["result"]
        self.assertEqual(out["entries"][0], prior)
        self.assertEqual(out["entries"][1]["customType"], "anchorloop-close-guard")


if __name__ == "__main__":
    unittest.main()
