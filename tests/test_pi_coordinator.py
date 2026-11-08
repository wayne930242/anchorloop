"""A loop book that tracks a coordinator: links, landings by ref state, checkpoints, children from evidence, orphans, units."""

import json
import subprocess
import unittest
from pathlib import Path

from tests.pi_harness import bash_result, stage, todo_create, tool_result
from tests.test_pi_book import BookCase, edit, text_of


def spawn(child: str, name: str, session_file: str | None = None, cwd: str | None = None, **details) -> dict:
    """A `subagent` tool result carrying pi-herdr-agents' started metadata."""
    started = {"id": child, "name": name, "agent": "worker", "task": "work", "status": "started", **({"sessionFile": session_file} if session_file else {}), **details}
    return tool_result("subagent", {"cwd": cwd} if cwd else {}, "started", details=started)


def returned(name: str, session_file: str | None = None, text: str = "done", agent: str = "worker", **details) -> dict:
    """A `subagent_result` custom message as the host delivers it."""
    body = {"name": name, "agent": agent, "resultContent": text, "task": "work", "exitCode": 0, **({"sessionFile": session_file} if session_file else {}), **details}
    return {"event": "message_end", "payload": {"message": {"role": "custom", "customType": "subagent_result", "details": body}}}


class CoordinatorCase(BookCase):
    """A coordinator clone of a bare remote, with `main` pushed, and helpers for worker worktrees."""

    def sh(self, *args: str, where: Path | None = None) -> str:
        return subprocess.run(["git", "-C", str(where or self.cwd), *args], check=True, capture_output=True, text=True).stdout.strip()

    @property
    def root(self) -> Path:
        return self.cwd.parent

    def shared_repo(self) -> None:
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.cwd)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args)
        (self.cwd / "app.py").write_text("print(1)\n")
        self.sh("add", "app.py")
        self.sh("commit", "-qm", "base")
        self.sh("remote", "add", "origin", str(remote))
        self.sh("push", "-q", "-u", "origin", "main")

    def worktree(self, name: str = "wt", branch: str = "feature", start: str = "HEAD") -> Path:
        tree = self.root / name
        self.sh("worktree", "add", "-q", "-b", branch, str(tree), start)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=tree)
        return tree

    def commit_in(self, tree: Path, path: str = "app.py", text: str = "print(2)\n", message: str = "feature") -> str:
        (tree / path).write_text(text)
        self.sh("add", path, where=tree)
        self.sh("commit", "-qm", message, where=tree)
        return self.sh("rev-parse", "HEAD", where=tree)

    def advance_origin(self, count: int = 1) -> None:
        """Commits `count` changes to origin/main from a second clone, then fetches them here."""
        other = self.root / "other-clone"
        if not other.exists():
            subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
            for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
                self.sh(*args, where=other)
        for i in range(count):
            (other / f"up{i}-{len(list(other.iterdir()))}.txt").write_text("x\n")
            self.sh("add", "-A", where=other)
            self.sh("commit", "-qm", "upstream", where=other)
        self.sh("push", "-q", "origin", "main", where=other)
        self.sh("fetch", "-q", "origin")

    def links(self) -> list[dict]:
        return self.entries("link")

    def closed_summary(self, *steps: dict) -> dict:
        """The session entry a close appends, after replaying `steps` over a loop whose only todo is done."""
        out = self.replay([*steps, stage(stage="close", verdict="landed")])
        return out["appended"][-1]["data"]


def done_loop(case: BookCase, anchor: str = "pytest -q") -> list[dict]:
    """A loop whose todo is already completed, so a `close` is accepted."""
    return [stage(stage="kind", kind="inline", intent="coordinate", anchor=anchor), todo_create("unit", status="completed")]


class TestLinks(CoordinatorCase):
    def test_a_link_records_the_session_file_cwd_worktree_and_the_integration_ref_with_its_sha_at_spawn(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        self.replay([*done_loop(self), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)])
        (link,) = self.links()
        self.assertEqual((link["child"], link["name"], link["agent"], link["sessionFile"]), ("kid", "w1", "worker", "/s/kid.jsonl"))
        self.assertEqual(link["worktree"], worktree)
        self.assertEqual(Path(link["cwd"]).resolve(), self.cwd.resolve())
        self.assertEqual((link["ref"], link["refSha"]), ("origin/main", base))

    def test_a_base_ref_other_than_head_is_the_integration_ref_and_a_repo_without_one_records_none(self):
        self.shared_repo()
        worktree = {"path": str(self.root / "gone"), "branch": "f", "baseRef": "origin/main", "baseSha": self.sh("rev-parse", "HEAD")}
        self.replay([*done_loop(self), spawn("kid", "w1", worktree=worktree)])
        self.assertEqual(self.links()[0]["ref"], "origin/main")

    def test_without_a_remote_the_link_has_no_ref(self):
        self.git_repo()
        self.replay([*done_loop(self), spawn("kid", "w1")])
        self.assertNotIn("ref", self.links()[0])

    def test_a_worktree_child_adds_a_base_at_its_base_sha_and_the_diff_includes_its_change(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        self.commit_in(tree)
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        data = self.closed_summary(*done_loop(self), spawn("kid", "w1", worktree=worktree))
        self.assertIn("wt: 1 file changed", data["diff"])

    def test_the_link_base_is_recorded_once_per_repo_with_via_link_and_the_child(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        self.replay([*done_loop(self), spawn("kid", "w1", worktree=worktree), spawn("kid", "w1", worktree=worktree)])
        linked = [entry for entry in self.entries("base") if entry.get("via") == "link"]
        self.assertEqual(len(linked), 1)
        self.assertEqual((Path(linked[0]["repo"]).resolve(), linked[0]["head"], linked[0]["child"]), (tree.resolve(), base, "kid"))

    def test_a_child_working_in_another_repo_adds_a_base_for_that_repo(self):
        self.shared_repo()
        other = self.root / "expense-app"
        other.mkdir()
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        (other / "x.txt").write_text("x\n")
        self.sh("add", "x.txt", where=other)
        self.sh("commit", "-qm", "base", where=other)
        head = self.sh("rev-parse", "HEAD", where=other)
        self.replay([*done_loop(self), spawn("kid", "w2", cwd=str(other))])
        linked = [entry for entry in self.entries("base") if entry.get("via") == "link"]
        self.assertEqual([(Path(entry["repo"]).resolve(), entry["head"]) for entry in linked], [(other.resolve(), head)])

    def test_the_diff_keeps_the_handoff_line_once_the_worktree_is_gone(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        head = self.commit_in(tree)
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        handoff = {"headSha": head, "commitsAhead": 1, "changedFiles": ["app.py"]}
        self.replay([*done_loop(self), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree), returned("w1", "/s/kid.jsonl", worktree=handoff)])
        self.sh("worktree", "remove", "--force", str(tree))
        data = self.closed_summary()
        self.assertIn("wt: 1 commit ahead at " + head[:9], data["diff"])
        self.assertNotIn("diff unavailable", data["diff"])

    def test_read_notes_how_far_behind_the_integration_ref_a_worker_was_based(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        self.advance_origin(2)
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        text = self.read_text([*self.open_loop(), spawn("kid", "mp4367-hq-worker", worktree=worktree)])
        self.assertIn("mp4367-hq-worker based 2 behind origin/main", text)

    def test_read_has_no_behind_note_for_a_worker_based_on_the_ref_tip(self):
        self.shared_repo()
        tree = self.worktree()
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.sh("rev-parse", "HEAD")}
        self.assertNotIn("behind", self.read_text([*self.open_loop(), spawn("kid", "w1", worktree=worktree)]))

    def test_a_returned_result_is_recorded_matched_by_session_file_then_by_name(self):
        self.replay([*self.open_loop(), spawn("kid-a", "alpha", "/s/a.jsonl"), spawn("kid-b", "beta", "/s/b.jsonl"),
                     returned("renamed", "/s/b.jsonl", worktree={"headSha": "f" * 40}), returned("alpha", None, exitCode=1)])
        results = self.entries("result")
        self.assertEqual([(entry["child"], entry["failed"]) for entry in results], [("kid-b", False), ("kid-a", True)])
        self.assertEqual(results[0]["headSha"], "f" * 40)

    def test_a_spawn_before_the_first_todo_is_linked_when_the_loop_opens(self):
        branch = [
            {"type": "message", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "tc1", "name": "subagent", "arguments": {"cwd": str(self.cwd)}}]}},
            {"type": "message", "message": {"role": "toolResult", "toolName": "subagent", "toolCallId": "tc1", "details": {"id": "kid", "name": "early", "agent": "worker", "sessionFile": "/s/early.jsonl", "status": "started"}}},
        ]
        self.replay([todo_create()], branch=branch)
        (link,) = self.links()
        self.assertEqual((link["child"], link["name"], link["sessionFile"]), ("kid", "early", "/s/early.jsonl"))
        self.assertEqual(link["cwd"], str(self.cwd))

    def test_a_spawn_that_already_returned_or_belongs_to_an_earlier_closed_loop_is_not_linked(self):
        started = lambda child, name, call: {"type": "message", "message": {"role": "toolResult", "toolName": "subagent", "toolCallId": call, "details": {"id": child, "name": name, "agent": "worker", "sessionFile": f"/s/{name}.jsonl", "status": "started"}}}
        done = {"type": "custom_message", "customType": "subagent_result", "details": {"name": "finished", "agent": "worker", "sessionFile": "/s/finished.jsonl"}}
        closed = {"type": "custom", "customType": "anchorloop-loop", "data": {"verdict": "landed"}}
        branch = [started("k0", "old", "c0"), closed, started("k1", "finished", "c1"), started("k2", "running", "c2"), done]
        self.replay([todo_create()], branch=branch)
        self.assertEqual([entry["name"] for entry in self.links()], ["running"])

    def test_a_kind_call_that_opens_the_loop_replays_prior_spawns_too(self):
        branch = [{"type": "message", "message": {"role": "toolResult", "toolName": "subagent", "toolCallId": "c1", "details": {"id": "kid", "name": "early", "agent": "worker", "status": "started"}}}]
        self.replay([stage(stage="kind", kind="inline", intent="x")], branch=branch)
        self.assertEqual([entry["child"] for entry in self.links()], ["kid"])


if __name__ == "__main__":
    unittest.main()
