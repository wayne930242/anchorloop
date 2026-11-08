"""A loop book that tracks a coordinator: links, landings by ref state, checkpoints, children from evidence, orphans, units."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.pi_harness import SETTLE, bash_call, bash_result, run, stage, todo_create, todo_state, tool_call, tool_result
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

    def wrapper(self) -> dict:
        """A `git` on PATH that logs each call's arguments, so a test counts the spawns."""
        import shutil
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        log = self.root / "git.log"
        log.unlink(missing_ok=True)
        script = bin_dir / "git"
        script.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\nexec {shutil.which("git")} "$@"\n')
        script.chmod(0o755)
        self.gitlog = log
        return {"PATH": f"{bin_dir}:{self.env()['PATH']}"}

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


class LandingCase(CoordinatorCase):
    """A coordinator with one linked worker whose commit sits in a worktree, its passing check recorded in a child book."""

    ANCHOR = "pytest -q"
    OBSERVE: list[str] | None = None

    def opening(self) -> list[dict]:
        """The loop's first steps: the kind call carrying the run anchor and, when a test sets them, the observe checkpoints."""
        extra = {"observe": self.OBSERVE} if self.OBSERVE else {}
        return [stage(stage="kind", kind="inline", intent="fix the export", anchor=self.ANCHOR, **extra), todo_create()]

    def start(self, commits: int = 1, check: bool = True) -> Path:
        self.shared_repo()
        self.tree = self.worktree()
        self.base = self.sh("rev-parse", "HEAD")
        files = [("app.py", "print(2)\n"), ("b.py", "b = 1\n")]
        for path, text in files[:commits]:
            self.head = self.commit_in(self.tree, path, text, f"change {path}")
        worktree = {"path": str(self.tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.base}
        self.replay([*self.opening(), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)])
        if check:
            self.child_check()
        return self.tree

    def child_check(self) -> None:
        main, self.cwd = self.cwd, self.tree
        try:
            self.replay([*self.open_loop("inline", "child work", anchor=self.ANCHOR), edit("app.py"), bash_result(self.ANCHOR, 0, "5 passed")],
                        env={"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w1"})
        finally:
            self.cwd = main

    def main_book(self) -> Path:
        return next(path for path in self.book_files() if "agents" not in path.parts)

    def lands(self) -> list[dict]:
        return self.entries("land", self.main_book())

    def phase_line(self, *steps: dict) -> str:
        return text_of(self.replay([*steps, stage(stage="read")])["results"][-1]).splitlines()[0]

    def bash(self, *effects: dict, command: str = "land-it") -> list[dict]:
        """The steps of one bash call: the tool_call, what the command did to the repos, and the result."""
        return [bash_call(command), *effects, bash_result(command, 0, "ok")]

    def push_from_worktree(self) -> list[dict]:
        return self.bash(run("git", "push", "-q", "origin", "HEAD:main", where=str(self.tree)))

    def integrator_picks(self, *shas: str) -> None:
        """Another clone cherry-picks `shas` onto the current origin/main and pushes, then this checkout fetches."""
        other = self.root / "integrator"
        if not other.exists():
            subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
            for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
                self.sh(*args, where=other)
        self.sh("fetch", "-q", "origin", where=other)
        self.sh("fetch", "-q", str(self.tree), "feature", where=other)
        self.sh("merge", "-q", "--ff-only", "origin/main", where=other)
        for sha in shas:
            self.sh("cherry-pick", "-x", sha, where=other)
        self.sh("push", "-q", "origin", "HEAD:main", where=other)
        self.sh("fetch", "-q", "origin")


class TestLanding(LandingCase):
    def test_a_push_from_the_worktree_is_a_landing_the_coordinator_made_with_the_tree_the_worker_checked(self):
        self.start()
        self.assertEqual(self.phase_line(*self.push_from_worktree()), "inline \u00b7 phase verify \u2713 \u2192 close")
        (land,) = self.lands()
        self.assertEqual((land["child"], land["rule"], land["exact"], land["self"], land["ref"]), ("kid", "ancestor", True, True, "origin/main"))
        self.assertEqual(self.entries("verify", self.main_book())[-1]["adopted"], "w1")

    def test_a_worker_landing_with_core_logallrefupdates_off_still_lands(self):
        self.shared_repo()
        self.sh("config", "core.logAllRefUpdates", "false")
        self.tree = self.worktree()
        self.base = self.sh("rev-parse", "HEAD")
        self.head = self.commit_in(self.tree, "app.py", "print(2)\n", "change app.py")
        worktree = {"path": str(self.tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.base}
        self.replay([*self.opening(), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)])
        self.phase_line(*self.push_from_worktree())
        self.assertEqual([entry["child"] for entry in self.lands()], ["kid"])

    def test_a_landing_is_the_act_of_a_coordinator_whose_worker_opened_no_book(self):
        self.start(check=False)
        self.assertIn("phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q`", self.phase_line(*self.push_from_worktree()))
        (land,) = self.lands()
        self.assertEqual((land["rule"], land["exact"], land["self"]), ("ancestor", False, True))

    def test_a_worker_rebased_by_the_coordinator_onto_a_moved_main_needs_the_coordinators_own_run(self):
        self.start()
        self.advance_origin(1)
        pick = self.bash(run("git", "checkout", "-q", "-B", "land", "origin/main"), run("git", "cherry-pick", self.head), run("git", "push", "-q", "origin", "HEAD:main"))
        self.assertIn("\u2192 verify (missing: a passing run of `pytest -q`", self.phase_line(*pick))
        (land,) = self.lands()
        self.assertEqual((land["rule"], land["exact"], land["self"]), ("patch-id", False, True))
        self.assertEqual(self.phase_line(bash_result("pytest -q", 0, "ok")), "inline \u00b7 phase verify \u2713 \u2192 close")

    def test_a_workers_later_failing_run_of_the_anchor_keeps_its_earlier_pass_from_being_adopted(self):
        self.start()
        main, self.cwd = self.cwd, self.tree
        try:
            self.replay([bash_result(self.ANCHOR, 1, "1 failed")], env={"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w1"})
        finally:
            self.cwd = main
        self.assertIn("\u2192 verify (missing: a passing run of `pytest -q`", self.phase_line(*self.push_from_worktree()))
        self.assertEqual([entry for entry in self.entries("verify", self.main_book()) if entry.get("adopted")], [])

    def test_a_worker_with_no_commits_of_its_own_that_updated_its_branch_from_main_is_not_landed_when_main_moves(self):
        self.start(commits=0)
        self.advance_origin(1)
        self.replay([{"event": "session_start", "payload": {}}])
        self.sh("merge", "-q", "--ff-only", "origin/main", where=self.tree)
        self.advance_origin(1)
        out = self.replay([{"event": "session_start", "payload": {}}, stage(stage="read")])
        self.assertEqual(self.lands(), [])
        self.assertEqual([entry for entry in self.entries("verify", self.main_book()) if entry.get("adopted")], [])
        self.assertNotIn("landed w1", text_of(out["results"][-1]))
        # Its real change lands later and is still watched.
        self.sh("merge", "-q", "--ff-only", "origin/main", where=self.tree)
        self.commit_in(self.tree, "real.py", "x = 1\n", "real work")
        self.sh("push", "-q", "origin", "HEAD:main", where=self.tree)
        self.sh("fetch", "-q", "origin")
        self.replay([{"event": "session_start", "payload": {}}])
        self.assertEqual([(entry["child"], entry["rule"]) for entry in self.lands()], [("kid", "ancestor")])

    def test_a_worker_that_fetches_and_fast_forwards_in_one_step_before_any_commit_of_its_own_is_never_landed(self):
        # The worker's fetch moves the refs it shares with this checkout, so no intermediate tip is ever seen.
        self.start(commits=0)
        self.upstream_push("integrator9")
        self.sh("fetch", "-q", "origin", where=self.tree)
        self.sh("merge", "-q", "--ff-only", "origin/main", where=self.tree)
        out = self.replay([*self.bash(command="ls"), stage(stage="read")])
        self.assertEqual(self.lands(), [])
        self.assertEqual([entry for entry in self.entries("verify", self.main_book()) if entry.get("adopted")], [])
        self.assertNotIn("landed w1", text_of(out["results"][-1]))
        # Its real change lands later and is still watched.
        self.commit_in(self.tree, "real.py", "x = 1\n", "real work")
        self.sh("push", "-q", "origin", "HEAD:main", where=self.tree)
        self.sh("fetch", "-q", "origin")
        self.replay([{"event": "session_start", "payload": {}}])
        self.assertEqual([(entry["child"], entry["rule"]) for entry in self.lands()], [("kid", "ancestor")])

    def test_a_worker_that_switches_to_its_own_branch_and_commits_is_landed(self):
        self.start(commits=0, check=False)
        self.sh("switch", "-q", "-c", "mp-1-fix", where=self.tree)
        self.commit_in(self.tree, "app.py", "print(2)\n", "fix")
        self.child_check()
        self.phase_line(*self.push_from_worktree())
        self.assertEqual([(entry["child"], entry["rule"]) for entry in self.lands()], [("kid", "ancestor")])

    def test_a_worker_that_commits_on_a_detached_head_is_landed(self):
        self.start(commits=0, check=False)
        self.sh("checkout", "-q", "--detach", where=self.tree)
        self.commit_in(self.tree, "app.py", "print(2)\n", "fix")
        self.child_check()
        self.phase_line(*self.push_from_worktree())
        self.assertEqual([(entry["child"], entry["rule"]) for entry in self.lands()], [("kid", "ancestor")])

    def test_a_worker_on_a_branch_made_from_a_pushed_branch_with_commits_from_another_clone_is_landed(self):
        self.shared_repo()
        other = self.root / "elsewhere"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        self.sh("switch", "-q", "-c", "feat-x", where=other)
        (other / "app.py").write_text("print(2)\n")
        self.sh("commit", "-qam", "earlier worker", where=other)
        self.sh("push", "-q", "origin", "feat-x", where=other)
        self.sh("fetch", "-q", "origin")
        self.base = self.sh("rev-parse", "origin/main")
        self.tree = self.worktree(branch="feature", start="origin/feat-x")
        worktree = {"path": str(self.tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.base}
        self.replay([*self.opening(), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)])
        self.child_check()
        self.phase_line(*self.push_from_worktree())
        self.assertEqual([(entry["child"], entry["rule"]) for entry in self.lands()], [("kid", "ancestor")])

    def test_an_untracked_file_does_not_reopen_verify_when_the_coordinators_push_holds_the_tree_it_checked(self):
        self.start(check=False)
        (self.cwd / "own.py").write_text("o = 1\n")
        self.sh("add", "own.py")
        self.sh("commit", "-qm", "own change")
        self.replay([edit("own.py"), bash_result(self.ANCHOR, 0, "ok")])
        (self.cwd / "notes.txt").write_text("todo\n")
        line = self.phase_line(*self.bash(run("git", "push", "-q", "origin", "HEAD:main")))
        self.assertEqual(line, "inline \u00b7 phase verify \u2713 \u2192 close")
        self.assertTrue([entry for entry in self.lands() if "child" not in entry][0]["exact"])

    def upstream_push(self, name: str = "integrator2") -> None:
        """Another clone pushes a commit to origin/main without this checkout fetching it."""
        other = self.root / name
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        (other / "up.txt").write_text("x\n")
        self.sh("add", "-A", where=other)
        self.sh("commit", "-qm", "upstream", where=other)
        self.sh("push", "-q", "origin", "main", where=other)

    def test_the_coordinators_own_fetch_of_an_integrators_landing_is_landed_elsewhere_and_the_workers_run_stands(self):
        self.start()
        self.advance_origin(1)
        self.replay([{"event": "session_start", "payload": {}}])
        other = self.root / "integrator3"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        self.sh("fetch", "-q", str(self.tree), "feature", where=other)
        self.sh("cherry-pick", "-x", self.head, where=other)
        self.sh("push", "-q", "origin", "HEAD:main", where=other)
        line = self.phase_line(*self.bash(run("git", "fetch", "-q", "origin"), command="git fetch origin"))
        (land,) = self.lands()
        self.assertEqual((land["child"], land["self"]), ("kid", False))
        self.assertEqual(line, "inline \u00b7 phase verify \u2713 \u2192 close")

    def test_a_pull_that_brings_in_upstream_commits_is_no_landing_of_the_coordinators_own_commits(self):
        self.start()
        self.upstream_push()
        self.replay(self.bash(run("git", "pull", "-q", "--ff-only"), command="git pull"))
        self.assertEqual([entry for entry in self.lands() if "child" not in entry], [])

    def test_each_bash_call_costs_one_ref_lookup_per_repo_however_many_refs_are_watched(self):
        self.start()
        self.sh("update-ref", "refs/remotes/origin/release", self.base)
        self.replay([spawn("kid2", "w2", worktree={"path": str(self.tree), "branch": "feature", "baseRef": "origin/release", "baseSha": self.base})])
        env = self.wrapper()
        self.replay([*self.bash(command="ls"), *self.bash(command="ls")], env=env)
        calls = self.gitlog.read_text().splitlines() if self.gitlog.exists() else []
        self.assertLessEqual(len([call for call in calls if "@{upstream}" in call]), 1, calls)
        self.assertLessEqual(len(calls), 5, calls)

    def test_a_squash_landing_is_proven_by_the_content_of_every_path_it_touched(self):
        self.start(commits=2)
        other = self.root / "squasher"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        (other / "app.py").write_text("print(2)\n")
        (other / "b.py").write_text("b = 1\n")
        self.sh("add", "-A", where=other)
        self.sh("commit", "-qm", "squash", where=other)
        self.sh("push", "-q", "origin", "main", where=other)
        self.sh("fetch", "-q", "origin")
        self.replay([{"event": "session_start", "payload": {}}])
        (land,) = self.lands()
        self.assertEqual((land["rule"], land["self"]), ("content", False))

    def test_one_of_two_commits_upstream_is_no_landing_and_read_shows_the_part(self):
        self.start(commits=2)
        first = self.sh("rev-list", "--reverse", f"{self.base}..{self.head}", where=self.tree).splitlines()[0]
        self.integrator_picks(first)
        text = text_of(self.replay([{"event": "session_start", "payload": {}}, stage(stage="read")])["results"][-1])
        self.assertEqual(self.lands(), [])
        self.assertIn("w1: partial 1/2 in origin/main", text)

    def test_an_integrators_landing_fetched_here_is_recorded_as_another_owners_and_the_workers_run_stands(self):
        self.start()
        self.integrator_picks(self.head)
        line = self.phase_line({"event": "session_start", "payload": {}})
        (land,) = self.lands()
        self.assertEqual((land["rule"], land["self"]), ("patch-id", False))
        self.assertEqual(line, "inline \u00b7 phase verify \u2713 \u2192 close")

    def test_an_integrator_that_moved_main_first_still_leaves_the_workers_run_standing(self):
        self.start()
        self.advance_origin(1)
        self.integrator_picks(self.head)
        line = self.phase_line({"event": "session_start", "payload": {}})
        (land,) = self.lands()
        self.assertEqual((land["self"], land["exact"]), (False, False))
        self.assertEqual(line, "inline \u00b7 phase verify \u2713 \u2192 close")

    def test_the_coordinators_own_edit_after_the_spawn_keeps_the_workers_run_from_standing(self):
        self.start()
        self.replay([edit("lib.py")])
        self.integrator_picks(self.head)
        self.assertIn("\u2192 verify (missing", self.phase_line({"event": "session_start", "payload": {}}))

    def test_a_ref_that_moved_without_a_landing_records_nothing(self):
        self.start()
        self.advance_origin(1)
        self.replay([{"event": "session_start", "payload": {}}])
        self.assertEqual(self.lands(), [])

    def test_a_landed_notice_for_a_commit_not_in_the_ref_here_is_unverified_and_names_the_fetch(self):
        self.start(check=False)
        out = self.replay([stage(stage="landed", sha=self.head)])
        self.assertIn("is not in origin/main here (fetch it, or give `ref`)", text_of(out["results"][0]))
        (land,) = self.lands()
        self.assertIs(land["verified"], False)
        self.assertIn("act (missing", self.phase_line())

    def test_a_landed_notice_after_the_fetch_is_checked_by_the_rules_and_counts(self):
        self.start()
        self.integrator_picks(self.head)
        out = self.replay([stage(stage="landed", sha=self.sh("rev-parse", "origin/main"))])
        self.assertIn("w1", text_of(out["results"][0]))
        (land,) = [entry for entry in self.lands() if entry.get("verified")]
        self.assertEqual((land["child"], land["rule"], land["self"]), ("kid", "patch-id", False))
        self.assertEqual(self.phase_line(), "inline \u00b7 phase verify \u2713 \u2192 close")

    def test_a_landed_notice_with_no_sha_is_checked_against_the_watched_ref(self):
        self.start()
        self.integrator_picks(self.head)
        out = self.replay([stage(stage="landed", note="integrator says landed")])
        self.assertTrue(text_of(out["results"][0]).startswith("recorded") or text_of(out["results"][0]).startswith("already recorded"), text_of(out["results"][0]))
        self.assertEqual([entry["verified"] for entry in self.lands()], [True])

    def test_a_declared_landing_with_no_ref_labels_each_branch_with_the_ref_it_landed_in(self):
        self.start()
        tree2 = self.worktree("wt2", "feature2")
        head2 = self.commit_in(tree2, "c.py", "c = 1\n", "second")
        worktree2 = {"path": str(tree2), "branch": "feature2", "baseRef": "origin/release", "baseSha": self.base}
        self.sh("update-ref", "refs/remotes/origin/release", head2)
        self.replay([spawn("kid2", "w2", worktree=worktree2)])
        self.replay([stage(stage="landed", note="w2 landed")])
        landed = [(entry["label"], entry["ref"]) for entry in self.lands() if entry.get("verified") and "child" in entry]
        self.assertEqual(landed, [("w2", "origin/release")])

    def test_a_declared_sha_with_no_ref_must_be_in_every_watched_ref(self):
        self.start(check=False)
        self.sh("update-ref", "refs/remotes/origin/release", self.base)
        self.replay([spawn("kid2", "w2", worktree={"path": str(self.tree), "branch": "feature", "baseRef": "origin/release", "baseSha": self.base})])
        self.advance_origin(1)
        out = self.replay([stage(stage="landed", sha=self.sh("rev-parse", "origin/main"))])
        self.assertTrue(text_of(out["results"][0]).startswith("not confirmed"), text_of(out["results"][0]))
        self.assertIn("origin/release", text_of(out["results"][0]))
        self.assertIn("or give `ref`", text_of(out["results"][0]))
        self.assertNotIn("origin/main", text_of(out["results"][0]))
        self.assertEqual([entry for entry in self.lands() if entry.get("verified")], [])

    def test_a_declared_sha_in_the_ref_that_no_watched_branch_explains_is_recorded_but_is_not_the_act(self):
        self.start(check=False)
        before = self.phase_line()
        self.advance_origin(1)
        out = self.replay([stage(stage="landed", sha=self.sh("rev-parse", "origin/main"))])
        self.assertTrue(text_of(out["results"][0]).startswith("recorded"), text_of(out["results"][0]))
        self.assertEqual([entry["rule"] for entry in self.lands()], ["declared"])
        self.assertEqual(self.phase_line(), before)

    def test_a_session_with_no_linked_worker_records_no_landing_of_its_own_commits(self):
        self.shared_repo()
        self.replay(self.open_loop(anchor="pytest -q"))
        (self.cwd / "app.py").write_text("print(3)\n")
        self.sh("commit", "-qam", "own change")
        steps = [edit("app.py"), bash_result("pytest -q", 0, "ok"), *self.bash(run("git", "push", "-q", "origin", "HEAD:main"))]
        self.assertEqual(self.phase_line(*steps), "inline \u00b7 phase verify \u2713 \u2192 close")
        self.assertEqual(self.lands(), [])

    def test_the_coordinators_own_commits_land_by_push_once_a_worker_is_linked(self):
        self.start(check=False)
        (self.cwd / "own.py").write_text("o = 1\n")
        self.sh("add", "own.py")
        self.sh("commit", "-qm", "own change")
        self.replay([edit("own.py")])
        self.replay(self.bash(run("git", "push", "-q", "origin", "HEAD:main")))
        own = [entry for entry in self.lands() if "child" not in entry]
        self.assertEqual([(entry["rule"], entry["self"]) for entry in own], [("ancestor", True)])

    def test_a_pull_on_a_watched_local_branch_is_no_landing_of_the_coordinators_own_commits(self):
        self.shared_repo()
        self.tree = self.worktree()
        self.base = self.sh("rev-parse", "HEAD")
        self.commit_in(self.tree, "app.py", "print(2)\n", "change")
        worktree = {"path": str(self.tree), "branch": "feature", "baseRef": "main", "baseSha": self.base}
        self.replay([*self.opening(), spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)])
        self.upstream_push("integrator8")
        self.replay(self.bash(run("git", "pull", "-q", "--ff-only"), command="git pull"))
        self.assertEqual(self.lands(), [])

    def test_a_pull_rebase_with_no_reflog_for_the_remote_ref_is_no_landing_of_the_coordinators_own_commits(self):
        import shutil
        self.start()
        self.sh("config", "core.logAllRefUpdates", "false")
        shutil.rmtree(self.cwd / ".git" / "logs" / "refs" / "remotes", ignore_errors=True)
        self.upstream_push("integrator6")
        self.replay(self.bash(run("git", "pull", "-q", "--rebase"), command="git pull --rebase"))
        self.assertEqual([entry for entry in self.lands() if "child" not in entry], [])


class TestPlainSession(CoordinatorCase):
    """A book with no host child links is read exactly as 2.10.1 read it, with no landing work."""

    # The git subcommands only landing detection runs; 2.10.1 ran none of them.
    LANDING_GIT = ("@{upstream}", "symbolic-ref", "cherry", "merge-base", "rev-list", "for-each-ref", "reflog")

    def upstream_commit(self) -> None:
        other = self.root / "other-clone"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(other)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        (other / "up.txt").write_text("x\n")
        self.sh("add", "-A", where=other)
        self.sh("commit", "-qm", "upstream", where=other)
        self.sh("push", "-q", "origin", "main", where=other)

    def test_edit_commit_untracked_pass_push_and_pull_read_as_2_10_1_read_them_with_no_landing_git_calls(self):
        env = self.wrapper()
        self.shared_repo()
        self.replay(self.open_loop(anchor="pytest -q"), env=env)
        seen: list[str] = []

        def step(*steps: dict) -> None:
            seen.append(text_of(self.replay([*steps, stage(stage="read")], env=env)["results"][-1]).splitlines()[0])

        step(tool_call("write", "app.py"), edit("app.py"))
        (self.cwd / "app.py").write_text("print(3)\n")
        step(bash_call("git commit -qam own"), run("git", "commit", "-qam", "own"), bash_result("git commit -qam own", 0, ""))
        (self.cwd / "notes.txt").write_text("todo\n")
        step(bash_result("pytest -q", 0, "ok"))
        step(bash_call("git push"), run("git", "push", "-q", "origin", "HEAD:main"), bash_result("git push", 0, ""))
        self.upstream_commit()
        step(bash_call("git pull"), run("git", "pull", "-q", "--ff-only"), bash_result("git pull", 0, "Fast-forward"))
        seen.append(text_of(self.replay([stage(stage="close", verdict="landed")], env=env, branch=[todo_state({"subject": "write the fix", "status": "completed"})])["results"][0]))
        # Captured by running this scenario on 72078f9.
        self.assertEqual(seen, [
            "inline \u00b7 phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q` after the last change)",
            "inline \u00b7 phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q` after the last change)",
            "inline \u00b7 phase verify \u2713 \u2192 close",
            "inline \u00b7 phase verify \u2713 \u2192 close",
            "inline \u00b7 phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q` after the last change)",
            "closed (landed). not complete: verify (a passing run of `pytest -q` after the last change). Clear the todo list.",
        ])
        calls = self.gitlog.read_text().splitlines()
        self.assertEqual([call for call in calls if any(word in call for word in self.LANDING_GIT) and not call.startswith(("push", "pull", "commit"))], [])


class TestObserve(LandingCase):
    """Post-land observations: each is closed by a `verify` naming its checkpoint, after the last landing."""

    OBSERVE = ["health returns 200", "row counts match"]

    def test_after_the_landing_the_first_open_observation_is_what_verify_lacks_until_each_is_declared(self):
        self.start()
        self.assertIn("phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q`", self.phase_line())
        self.assertEqual(self.phase_line(*self.push_from_worktree()), "inline \u00b7 phase act \u2713 \u2192 verify (missing: observe 1/2: health returns 200)")
        self.assertEqual(self.phase_line(stage(stage="verify", note="GET /health 200", checkpoint=1)), "inline \u00b7 phase act \u2713 \u2192 verify (missing: observe 2/2: row counts match)")
        self.assertEqual(self.phase_line(stage(stage="verify", note="588 rows both sides", checkpoint=2)), "inline \u00b7 phase verify \u2713 \u2192 close")
        self.assertEqual([entry["checkpoint"] for entry in self.entries("verify", self.main_book()) if "checkpoint" in entry], [1, 2])

    def test_an_observation_declared_before_the_landing_does_not_count_and_a_failed_one_stays_open(self):
        self.start()
        self.replay([stage(stage="verify", note="looks fine already", checkpoint=1)])
        self.assertIn("observe 1/2", self.phase_line(*self.push_from_worktree()))
        self.assertIn("observe 1/2", self.phase_line(stage(stage="verify", note="503", result="fail", checkpoint=1)))

    def test_a_checkpoint_number_the_loop_does_not_have_is_refused(self):
        self.start()
        out = self.replay([stage(stage="verify", note="x", checkpoint=3)])
        self.assertIn("checkpoint", out["results"][0]["error"])

    def test_observations_are_not_a_run_of_the_anchor(self):
        # A coordinator that never ran or adopted a run is not done because it observed.
        self.start(check=False)
        self.phase_line(*self.push_from_worktree())
        line = self.phase_line(stage(stage="verify", note="200", checkpoint=1), stage(stage="verify", note="rows", checkpoint=2))
        self.assertIn("verify (missing: a passing run of `pytest -q`", line)

    def test_the_first_todos_observe_metadata_is_the_loop_observe_list(self):
        self.replay([todo_create("ship it", anchor="pytest -q", observe=["page shows the column"])])
        self.assertEqual(self.entries("observe")[0]["items"], ["page shows the column"])


class TestNudge(CoordinatorCase):
    def stated(self, text: str) -> dict:
        return {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}}

    def test_a_prose_anchor_line_is_not_quoted_as_a_command_and_offers_verify(self):
        text = self.read_text([*self.open_loop(), self.stated("Reality anchor: expense-app tests green; after cutover 588 entries"), edit()])
        line = text.splitlines()[0]
        self.assertEqual(line, "inline \u00b7 phase act \u2713 \u2192 verify (missing: evidence for the anchor after the last change: a run of its command, or `verify` naming what you observed)")
        self.assertNotIn("`expense-app", line)

    def test_an_anchor_line_that_was_run_as_a_command_is_quoted_again_after_the_next_change(self):
        steps = [*self.open_loop(), self.stated("Reality anchor: pytest tests/x.py"), edit(), bash_result("pytest tests/x.py", 0, "ok"), edit()]
        self.assertIn("a passing run of `pytest tests/x.py` after the last change", self.read_text(steps))

    def test_an_anchor_on_the_kind_call_is_a_structured_run_and_stays_quoted(self):
        self.assertIn("a passing run of `make test` after the last change", self.read_text([*self.open_loop(anchor="make test"), edit()]))


class TestChildBook(CoordinatorCase):
    """A pi-herdr child opens its book from its first change or run of the unit's anchor, with no todo, so the coordinator sees it."""

    CHILD = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w1"}

    def coordinator(self, anchor: str = "pytest -q") -> None:
        self.git_repo()
        self.replay([*self.open_loop(anchor=anchor), spawn("kid", "w1", "/s/kid.jsonl")])

    def child_book(self) -> Path:
        return next(path for path in self.book_files() if "agents" in path.parts)

    def child_edit(self) -> list[dict]:
        return [tool_call("write", "src/app.py"), edit()]

    def test_a_childs_first_production_edit_opens_its_book_with_the_unit_anchor_and_no_todo(self):
        self.coordinator()
        self.replay(self.child_edit(), env=self.CHILD)
        header, entries = self.book(self.child_book())
        self.assertEqual(header["owner"], "w1")
        self.assertEqual([e["stage"] for e in entries if e["stage"] in ("kind", "anchor", "base", "edit")], ["base", "kind", "anchor", "edit"])
        self.assertEqual([e["check"] for e in entries if e["stage"] == "anchor"], ["pytest -q"])

    def test_a_reality_anchor_line_the_child_stated_before_its_first_edit_is_its_anchor_when_it_has_no_todo(self):
        self.git_repo()
        branch = [{"type": "message", "message": {"role": "user", "content": "fix it"}},
                  {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest tests/test_export.py"}]}}]
        self.replay(self.child_edit(), env=self.CHILD, branch=branch)
        self.assertEqual([e["check"] for e in self.entries("anchor", self.child_book())], ["pytest tests/test_export.py"])

    def test_a_childs_run_of_the_parents_anchor_is_a_check_with_the_trees_it_ran_on(self):
        self.coordinator()
        self.replay([*self.child_edit(), bash_result("pytest -q", 0, "5 passed")], env=self.CHILD)
        (check,) = self.entries("check", self.child_book())
        self.assertEqual((check["command"], check["exit"]), ("pytest -q", 0))
        self.assertEqual(len(check["trees"]), 1)

    def test_a_run_of_the_parents_anchor_alone_opens_the_childs_book(self):
        self.coordinator()
        self.replay([bash_result("pytest -q", 0, "5 passed")], env=self.CHILD)
        self.assertEqual([e["exit"] for e in self.entries("check", self.child_book())], [0])

    def test_the_coordinators_act_comes_from_the_childs_edit(self):
        self.coordinator()
        self.replay(self.child_edit(), env=self.CHILD)
        self.assertEqual(self.read_text([]).splitlines()[0], "inline \u00b7 phase act \u2713 \u2192 verify (missing: a passing run of `pytest -q` after the last change)")
        self.assertIn("child w1: inline; stages kind, anchor, act", self.read_text([]))

    def test_a_childs_commit_without_a_book_is_its_change(self):
        self.coordinator()
        (self.cwd / "app.py").write_text("print(2)\n")
        self.sh("commit", "-qam", "change")
        self.replay([bash_result("git commit -qam change", 0, "")], env=self.CHILD)
        self.assertEqual([e.get("via") for e in self.entries("edit", self.child_book())], ["commit"])

    def test_a_child_with_no_known_anchor_still_opens_its_book_on_an_edit_and_records_no_run(self):
        self.git_repo()
        self.replay([*self.child_edit(), bash_result("pytest -q", 0, "ok")], env=self.CHILD)
        self.assertEqual(self.entries("check", self.child_book()), [])
        self.assertEqual(len(self.entries("edit", self.child_book())), 1)

    def test_a_main_session_with_no_loop_still_opens_nothing_on_an_edit(self):
        self.git_repo()
        self.replay(self.child_edit())
        self.assertEqual(self.book_files(), [])

    def test_a_scratch_edit_or_a_foreign_command_does_not_open_a_childs_book(self):
        self.coordinator()
        self.replay([tool_call("write", "scratch/n.json"), tool_result("write", {"path": "scratch/n.json"}), bash_result("ls", 0, "x")], env=self.CHILD)
        self.assertEqual([path for path in self.book_files() if "agents" in path.parts], [])

    def test_an_env_only_child_opens_no_book_from_an_edit_or_a_commit_as_before_2_11(self):
        self.git_repo()
        env = {"PI_SUBAGENT_CHILD": "1"}
        self.replay(self.child_edit(), env=env)
        (self.cwd / "app.py").write_text("print(2)\n")
        self.sh("commit", "-qam", "change")
        self.replay([bash_result("git commit -qam change", 0, "")], env=env)
        self.assertEqual(self.book_files(), [])


class TestOrphans(CoordinatorCase):
    """A child whose result never arrived (its parent restarted, its watcher gone) is named, with what the host and the git state can tell."""

    SESSION = "/s/kid.jsonl"

    def process_record(self, pid: int | None) -> str:
        path = self.root / "kid.jsonl"
        if pid is not None:
            (self.root / "kid.jsonl.process.json").write_text(json.dumps({"version": 1, "pid": pid}))
        return str(path)

    def dead_pid(self) -> int:
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait()
        return process.pid

    def child_book(self, *steps: dict) -> None:
        self.replay([*self.open_loop("inline", "child work", anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "5 passed"), *steps],
                    env={"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "mp4366-worker"})

    def test_session_start_and_read_name_a_child_with_no_result_its_process_its_book_and_its_worktree(self):
        self.shared_repo()
        tree = self.worktree(branch="feat/mp-4366")
        base = self.sh("rev-parse", "HEAD")
        for n in range(3):
            self.commit_in(tree, f"f{n}.py", f"x = {n}\n", f"c{n}")
        session = self.process_record(self.dead_pid())
        worktree = {"path": str(tree), "branch": "feat/mp-4366", "baseRef": "HEAD", "baseSha": base}
        self.replay([*self.open_loop(anchor="pytest -q"), spawn("kid", "mp4366-worker", session, worktree=worktree)])
        self.child_book(stage(stage="close", verdict="landed"))
        out = self.replay([{"event": "session_start", "payload": {}}, stage(stage="read")])
        expected = "mp4366-worker: no result; process gone; child book closed (landed), check exit 0; worktree feat/mp-4366 ahead 3"
        self.assertIn(expected, "\n".join(notice["message"] for notice in out["notices"]))
        self.assertIn(expected, text_of(out["results"][-1]))

    def test_a_child_with_no_process_record_is_unknown_and_one_that_returned_is_not_named(self):
        self.replay([*self.open_loop(), spawn("kid", "w1", "/s/none.jsonl"), spawn("kid2", "w2", "/s/two.jsonl"), returned("w2", "/s/two.jsonl")])
        text = self.read_text([])
        self.assertIn("w1: no result; process unknown; no child book", text)
        self.assertNotIn("w2:", text)

    def test_a_link_from_before_2_11_reads_as_result_unknown_not_as_no_result(self):
        self.replay(self.open_loop())
        book = self.book_files()[0]
        book.write_text(book.read_text() + json.dumps({"ts": "2026-11-01T00:00:00.000Z", "stage": "link", "child": "old", "name": "legacy", "agent": "worker"}).join(["- ", "\n"]))
        text = self.read_text([])
        self.assertIn("legacy: result unknown (link has no cwd)", text)
        self.assertNotIn("legacy: no result", text)

    def test_a_live_process_is_alive(self):
        alive = subprocess.Popen(["sleep", "30"])
        try:
            session = self.process_record(alive.pid)
            self.replay([*self.open_loop(), spawn("kid", "w1", session)])
            self.assertIn("w1: no result; process alive", self.read_text([]))
        finally:
            alive.kill()
            alive.wait()

    def test_the_second_thought_snapshot_carries_the_count_of_children_without_a_result(self):
        self.replay([*self.open_loop(), spawn("kid", "w1", "/s/a.jsonl"), spawn("kid2", "w2", "/s/b.jsonl")])
        out = self.replay([SETTLE],
                          extensions=("book.ts", "second-thought.ts"), classify={"stopReason": "stop", "answers": {"move": {"type": "choice", "choice": "advance", "probabilities": {"advance": 0.7}}, "done": {"type": "bool", "probability": 0.9}, "review": {"type": "choice", "choice": "none", "probabilities": {"none": 0.6}}, "quality": {"type": "score", "score": 2.9}}})
        self.assertIn("2 children without a result", out["classifyCalls"][0]["verify"])


class TestUnits(CoordinatorCase):
    """Parallel tickets in one book: a todo with its own anchor, observations, kind, landing ref, or agents is a unit with its own phases."""

    ONE = {"subject": "MP-4366 expense export", "status": "in_progress", "metadata": {"anchor": "pytest -q", "kind": "reviewed", "lands": "origin/release", "agents": ["w1"]}}
    TWO = {"subject": "MP-4367 hq view", "status": "in_progress", "metadata": {"anchor": "make test", "observe": ["page loads"], "agents": ["w2"]}}

    def branch(self, *tasks: dict) -> list:
        return [todo_state(*(tasks or (self.ONE, self.TWO)))]

    def creates(self, *tasks: dict) -> list[dict]:
        return [todo_create(task["subject"], i + 1, task["status"], **task["metadata"]) for i, task in enumerate(tasks or (self.ONE, self.TWO))]

    def start(self, *tasks: dict, links: tuple[dict, ...] = ()) -> None:
        self.git_repo()
        self.replay([*self.creates(*tasks), *(links or (spawn("k1", "w1"), spawn("k2", "w2")))], branch=self.branch(*tasks))

    def child_edit(self, child: str, name: str) -> None:
        self.replay([tool_call("write", "src/app.py"), edit()], env={"PI_SUBAGENT_ID": child, "PI_SUBAGENT_NAME": name})

    def lines(self, *steps: dict, tasks: tuple[dict, ...] = ()) -> list[str]:
        return self.read_text(list(steps), branch=self.branch(*tasks)).splitlines()

    def test_two_units_read_as_one_line_each_and_the_loop_line_is_the_first_unit_not_done(self):
        self.start()
        lines = self.lines()
        self.assertIn("MP-4366 reviewed \u00b7 anchor \u2713 \u2192 act (missing: a change to the code)", lines)
        self.assertIn("MP-4367 inline \u00b7 anchor \u2713 \u2192 act (missing: a change to the code)", lines)
        self.assertTrue(lines[0].startswith("reviewed \u00b7 phase anchor \u2713 \u2192 act"), lines[0])

    def test_an_agent_named_in_the_metadata_binds_the_child_and_its_acts_count_for_that_unit_only(self):
        self.start()
        self.child_edit("k1", "w1")
        lines = self.lines()
        self.assertIn("MP-4366 reviewed \u00b7 act \u2713 \u2192 verify (missing: a passing run of `pytest -q` after the last change)", lines)
        self.assertIn("MP-4367 inline \u00b7 anchor \u2713 \u2192 act (missing: a change to the code)", lines)

    def test_a_units_own_kind_and_anchor_decide_its_next_phase(self):
        self.start()
        self.child_edit("k1", "w1")
        lines = self.lines(bash_result("pytest -q", 0, "ok"))
        self.assertIn("MP-4366 reviewed \u00b7 verify \u2713 \u2192 review (missing: a review round after the last change with Blocking: P0=0 P1=0)", lines)
        self.assertIn("MP-4367 inline \u00b7 anchor \u2713 \u2192 act (missing: a change to the code)", lines)

    def test_the_ticket_id_in_a_childs_name_binds_it_to_the_one_open_todo_that_holds_it(self):
        one = {**self.ONE, "metadata": {k: v for k, v in self.ONE["metadata"].items() if k != "agents"}}
        two = {**self.TWO, "metadata": {k: v for k, v in self.TWO["metadata"].items() if k != "agents"}}
        self.start(one, two, links=(spawn("k2", "mp4367-hq-worker"),))
        self.child_edit("k2", "mp4367-hq-worker")
        lines = self.lines(tasks=(one, two))
        self.assertIn("MP-4367 inline \u00b7 act \u2713 \u2192 verify (missing: a passing run of `make test` after the last change)", lines)
        self.assertIn("MP-4366 reviewed \u00b7 anchor \u2713 \u2192 act (missing: a change to the code)", lines)

    def test_a_ticket_id_two_open_todos_hold_binds_nothing_and_the_child_counts_for_every_unit(self):
        one = {**self.ONE, "metadata": {"anchor": "pytest -q", "kind": "inline"}}
        two = {**self.TWO, "metadata": {"anchor": "make test", "kind": "inline"}, "subject": "MP-4366 follow-up"}
        self.start(one, two, links=(spawn("k2", "mp4366-worker"),))
        self.child_edit("k2", "mp4366-worker")
        lines = self.lines(tasks=(one, two))
        unit_lines = [line for line in lines if line.startswith("MP-436") and "inline \u00b7" in line]
        self.assertEqual(len(unit_lines), 2, lines)
        self.assertTrue(all("act \u2713 \u2192 verify" in line for line in unit_lines), lines)

    def test_two_todos_that_carry_only_an_anchor_are_not_units_and_read_as_one_loop(self):
        a = {"subject": "fix a", "status": "in_progress", "metadata": {"anchor": "pytest a"}}
        b = {"subject": "fix b", "status": "pending", "metadata": {"anchor": "pytest b"}}
        self.git_repo()
        steps = [todo_create("fix a", 1, "in_progress", anchor="pytest a"), todo_create("fix b", 2, anchor="pytest b"), tool_call("write", "app.py"), edit("app.py"), bash_result("pytest a", 0, "ok")]
        lines = self.read_text(steps, branch=self.branch(a, b)).splitlines()
        self.assertTrue(lines[0].startswith("inline \u00b7 phase "), lines[0])
        self.assertFalse([line for line in lines if line.startswith(("#1 inline", "#2 inline"))], lines)
        out = self.replay([stage(stage="close", verdict="landed")], branch=[todo_state({**a, "status": "completed"}, {**b, "status": "completed"})])
        self.assertNotIn("#1 inline", text_of(out["results"][0]))

    def test_a_single_unit_loop_reads_as_before(self):
        self.git_repo()
        text = self.read_text([todo_create("MP-4366 export", 1, anchor="pytest -q")], branch=self.branch({"subject": "MP-4366 export", "status": "pending", "metadata": {"anchor": "pytest -q"}}))
        self.assertNotIn("MP-4366 inline", text)
        self.assertTrue(text.splitlines()[0].startswith("inline \u00b7 phase anchor \u2713 \u2192 act"))

    def test_a_units_observation_names_its_task_and_closes_only_that_units_checkpoint(self):
        self.start()
        out = self.replay([stage(stage="verify", note="loads", checkpoint=1, task=2)], branch=self.branch())
        self.assertEqual(self.entries("verify", next(p for p in self.book_files() if "agents" not in p.parts))[-1]["task"], 2)
        refused = self.replay([stage(stage="verify", note="loads", checkpoint=1, task=1)], branch=self.branch())
        self.assertIn("checkpoint", refused["results"][0]["error"])

    def test_a_units_landing_ref_is_the_ref_its_child_is_watched_against(self):
        self.shared_repo()
        self.replay([*self.creates(), spawn("k1", "w1")], branch=self.branch())
        self.assertEqual(self.links()[0]["ref"], "origin/release")

    def test_the_second_thought_state_carries_the_unit_lines_in_its_tasks_field(self):
        self.start()
        answers = {"stopReason": "stop", "answers": {"move": {"type": "choice", "choice": "advance", "probabilities": {"advance": 0.7}}, "done": {"type": "bool", "probability": 0.9}, "review": {"type": "choice", "choice": "none", "probabilities": {"none": 0.6}}, "quality": {"type": "score", "score": 2.9}}}
        out = self.replay([SETTLE], branch=self.branch(), extensions=("book.ts", "second-thought.ts"), classify=answers)
        self.assertIn("MP-4366 reviewed", out["classifyCalls"][0]["tasks"])
        self.assertIn("MP-4367 inline", out["classifyCalls"][0]["tasks"])

    def test_close_names_the_phases_every_unit_still_lacks(self):
        self.start()
        out = self.replay([stage(stage="close", verdict="blocked")], branch=[todo_state({**self.ONE, "status": "completed"}, {**self.TWO, "status": "completed"})])
        text = text_of(out["results"][0])
        self.assertIn("MP-4366 act", text)
        self.assertIn("MP-4367 act", text)


class TestGitTimeout(unittest.TestCase):
    def git_head(self, value: str) -> str:
        book = (Path(__file__).resolve().parent.parent / "pi" / "support" / "book.ts").as_uri()
        code = f'import {{ git }} from "{book}"; console.log(git(process.cwd(), ["rev-parse", "HEAD"]) ?? "none");'
        env = {**os.environ, "ANCHORLOOP_GIT_TIMEOUT_MS": value}
        return subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parent.parent).stdout.strip()

    def test_a_timeout_below_a_second_or_not_a_whole_number_falls_back_to_five_seconds(self):
        for value in ("1", "-5", "2500.5", "abc"):
            self.assertRegex(self.git_head(value), r"^[0-9a-f]{40}$", value)


if __name__ == "__main__":
    unittest.main()
