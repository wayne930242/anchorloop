"""The delegation-host seam: adapters for pi-herdr-agents, env-only markers, and no host at all."""

import json
import os
import shutil
import subprocess
import sys
import unittest

from tests.pi_harness import PI_DIR, stage, todo_create, tool_result
from tests.test_pi_book import BookCase, edit

HOST_URL = (PI_DIR / "support" / "host.ts").as_uri()

CALL = """
const host = await import(process.argv[1]);
const call = JSON.parse(process.argv[2]);
const env = call.env ?? {};
const detected = host.detectHost(env);
const out = {
  name: detected.name,
  isChild: host.isChild(env),
  childId: host.childId(env) ?? null,
  link: call.link ? host.linkFrom(call.link.tool, call.link.input, call.link.details) ?? null : null,
  result: call.message ? host.resultFrom(call.message) ?? null : null,
  liveness: call.live ? host.liveness(call.live) : null,
};
console.log(JSON.stringify(out));
"""

STARTED = {
    "id": "kid-1",
    "name": "mp4366-worker",
    "agent": "worker",
    "task": "do it",
    "sessionFile": "/tmp/sessions/kid-1.jsonl",
    "status": "started",
    "worktree": {"path": "/tmp/wt", "branch": "feat/x", "baseRef": "origin/main", "baseSha": "abc123", "manifestFile": "m.json"},
}


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extensions")
class TestHostAdapters(unittest.TestCase):
    def call(self, **call) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", CALL, HOST_URL, json.dumps(call)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_detection_picks_herdr_env_only_or_none_from_the_environment_alone(self):
        self.assertEqual(self.call(env={})["name"], "none")
        self.assertEqual(self.call(env={"PI_SUBAGENT_ID": "k"})["name"], "herdr")
        self.assertEqual(self.call(env={"PI_SUBAGENT_CHILD": "1"})["name"], "env-only")
        self.assertEqual(self.call(env={"PI_SUBAGENT_CHILD_AGENT": "a", "PI_SUBAGENT_PARENT_PID": "9"})["name"], "env-only")
        self.assertEqual(self.call(env={"PI_SUBAGENT_CHILD_AGENT": "a"})["name"], "none")

    def test_only_the_herdr_adapter_names_a_child_id_and_every_marker_makes_a_child(self):
        self.assertEqual(self.call(env={"PI_SUBAGENT_ID": "k"}), {**self.call(env={"PI_SUBAGENT_ID": "k"}), "isChild": True, "childId": "k"})
        env_only = self.call(env={"PI_SUBAGENT_CHILD": "1"})
        self.assertEqual((env_only["isChild"], env_only["childId"]), (True, None))
        none = self.call(env={})
        self.assertEqual((none["isChild"], none["childId"]), (False, None))

    def test_a_subagent_result_with_started_details_is_a_link_with_the_worktree_and_cwd(self):
        link = self.call(link={"tool": "subagent", "input": {"cwd": "/src/app"}, "details": STARTED})["link"]
        self.assertEqual(link["child"], "kid-1")
        self.assertEqual((link["name"], link["agent"], link["sessionFile"], link["cwd"]), ("mp4366-worker", "worker", "/tmp/sessions/kid-1.jsonl", "/src/app"))
        self.assertEqual(link["worktree"], {"path": "/tmp/wt", "branch": "feat/x", "baseRef": "origin/main", "baseSha": "abc123"})

    def test_other_tools_and_details_without_an_id_are_no_link(self):
        self.assertIsNone(self.call(link={"tool": "bash", "input": {}, "details": STARTED})["link"])
        self.assertIsNone(self.call(link={"tool": "subagent", "input": {}, "details": {"name": "x"}})["link"])
        self.assertIsNone(self.call(link={"tool": "subagent", "input": {}, "details": None})["link"])

    def test_a_subagent_result_message_becomes_a_result_and_a_nonzero_exit_is_a_failure(self):
        message = {"role": "custom", "customType": "subagent_result", "details": {"name": "w", "agent": "worker", "task": "t", "resultContent": "done", "sessionFile": "/s.jsonl", "exitCode": 0}}
        result = self.call(message=message)["result"]
        self.assertEqual((result["name"], result["agent"], result["failed"], result["sessionFile"]), ("w", "worker", False, "/s.jsonl"))
        failed = self.call(message={**message, "details": {**message["details"], "exitCode": 2}})["result"]
        self.assertTrue(failed["failed"])
        self.assertIsNone(self.call(message={"role": "assistant", "content": "x"})["result"])

    def test_liveness_is_unknown_without_a_process_record_gone_for_a_dead_pid_and_alive_for_a_live_one(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            session = str(Path(tmp) / "s.jsonl")
            link = {"child": "k", "sessionFile": session}
            self.assertEqual(self.call(live=link)["liveness"], "unknown")
            self.assertEqual(self.call(live={"child": "k"})["liveness"], "unknown")
            dead = subprocess.Popen([sys.executable, "-c", "pass"])
            dead.wait()
            Path(session + ".process.json").write_text(json.dumps({"version": 1, "pid": dead.pid}))
            self.assertEqual(self.call(live=link)["liveness"], "gone")
            alive = subprocess.Popen(["sleep", "30"])
            try:
                Path(session + ".process.json").write_text(json.dumps({"version": 1, "pid": alive.pid}))
                self.assertEqual(self.call(live=link)["liveness"], "alive")
            finally:
                alive.kill()
                alive.wait()


class TestNoHost(BookCase):
    """Without Straw Boss, pi-herdr-agents, or any subagent tool the book behaves as before and writes no link or orphan line."""

    def test_a_loop_with_no_subagent_tool_records_edits_and_reads_without_child_lines(self):
        text = self.read_text([*self.open_loop(anchor="pytest -q"), edit()])
        self.assertNotIn("child ", text)
        self.assertNotIn("no result", text)
        self.assertEqual(self.entries("link"), [])

    def test_a_subagent_tool_result_without_an_id_from_another_host_links_nothing(self):
        self.replay([*self.open_loop(), tool_result("subagent", {"agent": "x"}, "done", details={"results": []})])
        self.assertEqual(self.entries("link"), [])

    def test_an_env_only_child_opens_its_book_from_a_todo_and_links_nothing(self):
        self.replay([todo_create("child work"), edit()], env={"PI_SUBAGENT_CHILD": "1"})
        self.assertEqual(len(self.book_files()), 1)
        self.assertEqual(self.entries("link"), [])
        self.assertEqual(self.entries("edit")[0]["path"], "src/app.py")

    def test_the_herdr_spawn_signal_links_in_a_session_with_no_child_env(self):
        self.replay([*self.open_loop(), tool_result("subagent", {}, "started", details={"id": "kid", "name": "w", "agent": "worker", "status": "started"})])
        self.assertEqual([entry["child"] for entry in self.entries("link")], ["kid"])


if __name__ == "__main__":
    unittest.main()
