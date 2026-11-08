"""A loop book that tracks a coordinator: links, landings by ref state, checkpoints, children from evidence, orphans, units."""

import json
import subprocess
import unittest
from pathlib import Path

from tests.pi_harness import bash_call, bash_result, run, stage, todo_create, tool_result
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
        self.assertIn("Fetch origin/main", text_of(out["results"][0]))
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

    def test_a_session_with_no_workers_lands_its_own_commits_by_push_and_is_told_apart_from_a_fetch(self):
        self.shared_repo()
        self.replay(self.open_loop(anchor="pytest -q"))
        (self.cwd / "app.py").write_text("print(3)\n")
        self.sh("commit", "-qam", "own change")
        push = self.bash(run("git", "push", "-q", "origin", "HEAD:main"))
        steps = [edit("app.py"), bash_result("pytest -q", 0, "ok"), *push]
        self.assertEqual(self.phase_line(*steps), "inline \u00b7 phase verify \u2713 \u2192 close")
        (land,) = self.lands()
        self.assertNotIn("child", land)
        self.assertEqual((land["rule"], land["exact"], land["self"]), ("ancestor", True, True))


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


if __name__ == "__main__":
    unittest.main()
