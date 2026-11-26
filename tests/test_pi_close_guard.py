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
const pi = { getAllTools: () => [{ name: 'todo', parameters: { properties: JSON.parse(process.argv[4]) } }], on: (event, fn) => { (handlers[event] ??= []).push(fn); }, registerTool: (tool) => tools.push(tool.name) };
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


def user(content) -> dict:
    return {"type": "message", "id": f"u{abs(hash(str(content))) % 10**8}", "message": {"role": "user", "content": content}}


def monitor(call_id: str, command: str, monitor_id: str) -> list[dict]:
    return [call("MonitorCreate", call_id, command=command), result("MonitorCreate", call_id, text=f"Monitor #{monitor_id} started: {command}")]


def outcome(monitor_id: str, exit_code: int) -> dict:
    return {"type": "custom_message", "id": f"o{monitor_id}-{exit_code}", "customType": "pi-loop-monitor", "content": "done",
            "details": {"monitorOutcome": {"monitorId": monitor_id, "status": "completed", "exitCode": exit_code}}}


def edit(call_id: str, path: str = "src/app.py") -> list[dict]:
    return [call("edit", call_id, path=path), result("edit", call_id)]


def bash(call_id: str, command: str, ok: bool = True) -> list[dict]:
    return [call("bash", call_id, command=command), result("bash", call_id, is_error=not ok, text="" if ok else "Command exited with code 1")]


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extension")
class TestCloseGuard(unittest.TestCase):
    def settle(self, branch: list[dict], entries: list[dict] | None = None, ledger: bool = True) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", HARNESS, EXTENSION.as_uri(), json.dumps(branch), json.dumps(entries or []), json.dumps({"evidence": {}} if ledger else {})],
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

    def test_evidence_handoff_uses_real_results_and_the_current_task(self) -> None:
        task = {"id": 7, "subject": "check", "status": "in_progress", "anchor": "make check",
                "evidence": [{"command": "make check", "result": "pass", "at": "2026-01-01T00:00:00.000Z"}]}
        snapshot = {"type": "custom", "customType": "todo/v1", "data": {"v": 1, "tasks": [task], "nextId": 8}}
        branch = [call("todo", "t", action="update", id=7, anchor="make check"), snapshot, result("todo", "t"), *edit("e")]
        missing = self.settle(branch)["result"]["entries"][0]
        self.assertNotIn("evidence", missing["content"])
        passed = [*branch, missing, *bash("b", "make check")]
        line = self.notice(passed)
        self.assertIsNotNone(line)
        for token in ("todo update", "#7", "evidence", "command", "sha", '"pass"'):
            self.assertIn(token, line)
        self.assertIsNone(self.settle(passed, ledger=False)["result"])
        for command in ("echo make check", "make check || true"):
            self.assertIsNone(self.notice([*branch, *bash("b", command)]))
        reminder = self.settle(passed)["result"]["entries"][0]
        self.assertIsNone(self.notice([*passed, reminder]))
        self.assertIsNone(self.notice([*passed, say("Anchor: `make check`")]))
        empty = {**snapshot, "data": {"v": 1, "tasks": [], "nextId": 1}}
        self.assertIsNone(self.notice([*passed, empty, snapshot]))  # id reused after clear

    def test_batch_handoff_names_the_last_anchored_item(self) -> None:
        items = [{"subject": "one", "anchor": "make check"}, {"subject": "two", "metadata": {"anchor": "make check"}}, {"subject": "three"}]
        tasks = [{**item, "id": i, "status": "pending"} for i, item in enumerate(items, 1)]
        snapshot = {"type": "custom", "customType": "todo/v1", "data": {"v": 1, "tasks": tasks, "nextId": 4}}
        branch = [call("todo", "t", action="create", tasks=items), snapshot, result("todo", "t"), *edit("e")]
        self.assertIn("#2", self.notice([*branch, *bash("b", "cd svc && make check")]))
        rejected = [snapshot, call("todo", "u", action="update", id=1, anchor="make check"), result("todo", "u", is_error=True)]
        self.assertIsNone(self.notice([*rejected, *edit("e"), *bash("b", "make check")]))

    def test_a_failed_edit_is_not_a_change(self):
        branch = [say("Anchor: `pytest -q`"), *bash("b1", "pytest -q"), call("edit", "e1", path="a.py"), result("edit", "e1", is_error=True)]
        self.assertIsNone(self.notice(branch))

    def test_the_notice_is_not_repeated_for_the_same_change(self):
        branch = [say("Anchor: `pytest -q`"), *edit("e1")]
        first = self.settle(branch)["result"]["entries"][0]
        self.assertIsNone(self.notice([*branch, {"type": "custom_message", **first}]))
        self.assertIsNotNone(self.notice([*branch, {"type": "custom_message", **first}, *edit("e2")]))

    def test_labelled_check_lines_count_as_the_anchor(self):
        for line in ("Gates: `make check`", "**Checks:** `make check`", "## Verify: `make check`", "Done when: `make check` passes",
                     "驗證：`make check`", "- Reality anchor: `make check`"):
            with self.subTest(line=line):
                branch = [say(line), *edit("e1")]
                self.assertIn("`make check`", self.notice(branch))
                self.assertIsNone(self.notice([*branch, *bash("b1", "make check")]))

    def test_the_brief_states_the_anchor(self):
        for content in ("Fix the parser.\nAnchor: `make check`", [{"type": "text", "text": "Fix it.\nGates: `make check`"}]):
            with self.subTest(content=content):
                branch = [user(content), *edit("e1")]
                self.assertIn("`make check`", self.notice(branch))
                self.assertIsNone(self.notice([*branch, *bash("b1", "make check")]))
        later = [user("Fix it."), user("Anchor: `make check`"), *edit("e1")]
        self.assertIn("Anchor:", self.notice(later))

    def test_an_sb_check_spec_counts_as_the_anchor(self):
        spec = {"sb": {"spec": {"check": {"run": "make check"}}}}
        branch = [call("todo", "t1", action="create", subject="fix", metadata=spec), result("todo", "t1"), *edit("e1")]
        self.assertIn("`make check`", self.notice(branch))
        self.assertIsNone(self.notice([*branch, *bash("b1", "make check")]))

    def test_a_monitor_run_counts_by_its_exit_code(self):
        branch = [say("Anchor: `make check`"), *edit("e1"), *monitor("m1", "make check", "3")]
        self.assertIn("`make check`", self.notice(branch))
        self.assertIsNone(self.notice([*branch, outcome("3", 0)]))
        self.assertIn("`make check`", self.notice([*branch, outcome("3", 1)]))
        digest = {**outcome("3", 0), "details": {"notifications": [{"monitorOutcome": {"monitorId": "3", "exitCode": 0}}]}}
        self.assertIsNone(self.notice([*branch, digest]))

    def test_passing_evidence_after_the_last_change_counts(self):
        record = [call("todo", "t2", action="update", id=1, evidence=[{"command": "make check", "result": "pass"}]), result("todo", "t2")]
        anchored = [say("Anchor: `make check`"), *edit("e1")]
        self.assertIsNone(self.notice([*anchored, *record]))
        self.assertIsNone(self.notice([say("Fixing it."), *edit("e1"), *record]))
        self.assertIn("`make check`", self.notice([*anchored, *record, *edit("e2")]))
        failed = [call("todo", "t3", action="update", id=1, evidence=[{"command": "make check", "result": "fail"}]), result("todo", "t3")]
        self.assertIn("`make check`", self.notice([*anchored, *failed]))

    def test_prose_edits_after_the_check_do_not_rearm_it(self):
        branch = [say("Anchor: `make check`"), *edit("e1"), *bash("b1", "make check"), *edit("e2", "README.md"), *edit("e3", "notes/run.txt")]
        self.assertIsNone(self.notice(branch))
        self.assertIn("`make check`", self.notice([say("Anchor: `make check`"), *edit("e1", "docs/guide.md")]))

    def test_it_still_fires_when_nothing_was_stated(self):
        self.assertIn("Anchor:", self.notice([user("Fix the parser."), say("Done: the parser is fixed."), *edit("e1"), *bash("b1", "make check")]))

    def test_it_still_fires_when_the_anchor_failed_after_the_last_change(self):
        record = [call("todo", "t2", action="update", id=1, evidence=[{"command": "make check", "result": "pass"}]), result("todo", "t2")]
        branch = [user("Gates: `make check`"), *edit("e1"), *record, *bash("b1", "make check", ok=False)]
        self.assertIn("`make check`", self.notice(branch))
        self.assertIn("`make check`", self.notice([say("驗證：`make check`"), *edit("e1"), *monitor("m1", "make check", "4"), outcome("4", 2)]))

    def test_a_labelled_line_without_a_command_does_not_replace_the_anchor(self):
        for line in ("Summary.\nVerification: not run yet.", "**Checks:** reviewed the diff by eye", "檢查：稍後再跑"):
            with self.subTest(line=line):
                self.assertIn("`pytest -q`", self.notice([say("Anchor: `pytest -q`"), *edit("e1"), say(line)]))
        self.assertIn("Anchor:", self.notice([user("Fix the bug.\nVerify: the user confirms in the browser"), *edit("e1")]))
        spec = {"sb": {"spec": {"check": {"run": 3}}}}
        self.assertIn("Anchor:", self.notice([call("todo", "t1", action="create", subject="x", metadata=spec), result("todo", "t1"), *edit("e1")]))

    def test_evidence_for_another_command_does_not_pass_the_anchor(self):
        record = [call("todo", "t2", action="update", id=1, evidence=[{"command": "ls", "result": "pass"}]), result("todo", "t2")]
        branch = [say("Anchor: `pytest -q`"), *edit("e1"), *bash("b1", "pytest -q", ok=False), *record]
        self.assertIn("`pytest -q`", self.notice(branch))

    def test_it_still_fires_when_no_check_ran_after_a_code_change(self):
        branch = [say("Checks: `make check`"), *edit("e1", "README.md"), *bash("b1", "make check"), *edit("e2", "src/app.py"), *edit("e3", "CHANGELOG.md")]
        self.assertIn("`make check`", self.notice(branch))
        self.assertIn("`make check`", self.notice([say("Verify: `make check`"), *edit("e1"), *monitor("m1", "make check", "5")]))

    def test_earlier_proposed_entries_are_kept(self):
        prior = {"type": "custom", "customType": "other", "data": {}}
        out = self.settle([say("Anchor: `pytest -q`"), *edit("e1")], entries=[prior])["result"]
        self.assertEqual(out["entries"][0], prior)
        self.assertEqual(out["entries"][1]["customType"], "anchorloop-close-guard")


if __name__ == "__main__":
    unittest.main()
