"""Replays of the bug paths of the multitask model (docs/models/loop-book/multitask): a straw-boss coordinator with two units,
MP-1001 and MP-1002, each with its own anchor and its own worker. Each test walks one path of a check report on the real
extensions and asserts the rule at its end, in the reader's words.

Every test here is red on purpose: the model found the path on the code at 04f083a, and the fix is not part of this branch.
The rules are proposed; a rule the reader rejects takes its tests with it. Paths the twelve tests of test_model_loop_book.py
already walk (a turn another wake starts is judged while a worker is out; a verify with no `task`) are not repeated here.
"""

import subprocess

from tests.pi_harness import SETTLE, SETTLED, bash_call, bash_result, run, stage, todo_create, todo_state, tool_call, user_start
from tests.test_model_loop_book import CLEAR, jev_agrees
from tests.test_pi_book import edit, subagent_result, text_of
from tests.test_pi_coordinator import CoordinatorCase, returned, spawn

A_ANCHOR, B_ANCHOR = "pytest tests/export", "pytest tests/view"
ONE = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "kind": "reviewed", "agents": ["w1"]}}
TWO = {"subject": "MP-1002 view", "status": "in_progress", "metadata": {"anchor": B_ANCHOR, "kind": "reviewed", "agents": ["w2"]}}
W1 = {"PI_SUBAGENT_ID": "k1", "PI_SUBAGENT_NAME": "w1"}
W2 = {"PI_SUBAGENT_ID": "k2", "PI_SUBAGENT_NAME": "w2"}
NOTICE = ("book.ts", "second-thought.ts")


class MultitaskCase(CoordinatorCase):
    extensions = ("book.ts",)

    def branch(self, *tasks: dict) -> list:
        return [todo_state(*(tasks or (ONE, TWO)))]

    def creates(self, *tasks: dict) -> list[dict]:
        return [todo_create(task["subject"], i + 1, task["status"], **task["metadata"]) for i, task in enumerate(tasks or (ONE, TWO))]

    def start(self, *links: dict) -> None:
        """Two units, each bound to its worker by `agents`, both workers started."""
        self.git_repo()
        self.replay([*self.creates(), *(links or (spawn("k1", "w1"), spawn("k2", "w2")))], branch=self.branch())

    def worker_edits(self, env: dict, path: str = "src/app.py", *more: dict) -> None:
        self.replay([tool_call("write", path), edit(path), *more], env=env)

    def unit(self, label: str, *steps: dict, tasks: tuple[dict, ...] = (), **kwargs) -> str:
        """The unit's line in `read` after `steps`."""
        out = self.replay([*steps, stage(stage="read")], branch=self.branch(*tasks), **kwargs)
        return next(line for line in text_of(out["results"][-1]).splitlines() if line.startswith(label))

    @staticmethod
    def notices(out: dict) -> list[str]:
        return [entry["content"] for result in out["results"] if result for entry in result.get("entries", []) if entry["type"] == "custom_message"]


class TestM1AChildsResultCountsForItsOwnUnit(MultitaskCase):
    """M1 (Counted): what passed, came back clear, or landed for a unit counts for that unit."""

    def test_a_workers_passing_run_of_its_units_anchor_counts_for_that_unit(self):
        # check/small-today/report.md, Counted: MP-1002's worker edits in its worktree, runs MP-1002's anchor, it passes,
        # and the worker returns.
        self.start()
        self.worker_edits(W2, "src/app.py", bash_result(B_ANCHOR, 0, "5 passed"))
        after = self.unit("MP-1002", returned("w2"))
        self.assertIn("verify ✓", after,
                      f"worker w2 works for MP-1002 and its run of `{B_ANCHOR}` passed after its last edit; the book asks the coordinator to run it again: {after}")

    def test_a_persistent_reviewers_clear_verdict_on_the_second_unit_counts_for_that_unit(self):
        # check/cross-today/report.md, NotLent and Counted: one reviewer reads MP-1001, then is sent MP-1002; both come back clear.
        self.start()
        self.worker_edits(W1)
        self.worker_edits(W2)
        reviewer = spawn("r1", "rev")
        reviewer["payload"]["details"].update(agent="reviewer", task="review MP-1001 branch feature/export")
        first = self.unit("MP-1001", bash_result(A_ANCHOR, 0, "ok"), bash_result(B_ANCHOR, 0, "ok"), reviewer,
                          subagent_result("reviewer", "rev", CLEAR, task="review MP-1001 branch feature/export"))
        self.assertIn("review ✓", first)
        # The coordinator sends the same reviewer MP-1002 (subagent_send), and it comes back clear.
        after = self.unit("MP-1002", subagent_result("reviewer", "rev", CLEAR, task="review MP-1002 branch feature/view"))
        self.assertIn("review ✓", after,
                      f"the reviewer reported `Blocking: P0=0 P1=0` for MP-1002 after its last change; the book keeps it for MP-1001, the unit of the reviewer's first brief, and reads: {after}")


class TestM3OneUnitsChangeLeavesTheOtherAlone(MultitaskCase):
    """M3 (Isolation): one unit's change, or its returned car, never takes another unit's check or review away."""

    def test_the_coordinators_change_to_one_units_code_leaves_the_other_units_check(self):
        # check/cross-today/report.md, Isolation: MP-1002's worker edits in its own worktree and its check passes; the
        # coordinator then changes MP-1001's code in its own checkout.
        self.shared_repo()
        tree = self.worktree()
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.sh("rev-parse", "HEAD")}
        self.replay([*self.creates(), spawn("k2", "w2", worktree=worktree)], branch=self.branch())
        main, self.cwd = self.cwd, tree
        try:
            self.worker_edits(W2, "view.py")
        finally:
            self.cwd = main
        self.assertIn("verify ✓", self.unit("MP-1002", returned("w2"), bash_result(B_ANCHOR, 0, "5 passed")))
        after = self.unit("MP-1002", tool_call("write", "app.py"), edit("app.py"))
        self.assertIn("verify ✓", after,
                      f"the coordinator changed app.py for MP-1001; MP-1002's code is in {tree.name}, untouched since its check passed, and the book reads: {after}")

    def test_a_returned_car_reopens_only_its_own_unit(self):
        # check/cross-today/report.md, Isolation: both units pass their checks; sb returns MP-1001's car and the
        # coordinator declares back with MP-1001's task.
        self.start()
        self.worker_edits(W1)
        self.worker_edits(W2)
        self.assertIn("verify ✓", self.unit("MP-1002", bash_result(A_ANCHOR, 0, "ok"), bash_result(B_ANCHOR, 0, "ok")))
        answer = self.replay([stage(stage="back", phase="verify", reason="sb returned car MP-1001", task=1)], branch=self.branch())["results"][0]
        if "error" in answer:
            return  # A fix may refuse `back` with a task and name another way; then nothing was reopened.
        after = self.unit("MP-1002")
        self.assertIn("verify ✓", after, f"only MP-1001's car came back, and MP-1002's passed check is gone: {after}")


class TestM4OneNoticePerChange(MultitaskCase):
    """M4 (OnePerChange): at most one notice per unit and missing step per real change."""

    extensions = NOTICE

    def test_a_reload_does_not_send_the_same_notice_again(self):
        # check/notice-today/report.md, OnePerChange: the turn ends with a notice; you /reload after an install; someone
        # speaks to you; the turn ends again with nothing changed.
        self.git_repo()
        first = self.replay([user_start(), *self.creates(), tool_call("write", "app.py"), edit("app.py"), SETTLE], branch=self.branch(), classify=jev_agrees())
        self.assertEqual(len(self.notices(first)), 1, "the first turn end gives one notice")
        again = self.replay([{"event": "session_start", "payload": {"reason": "reload"}}, user_start("installed, carry on"), SETTLE],
                            branch=self.branch(), classify=jev_agrees())
        self.assertEqual(self.notices(again), [], f"nothing changed since the notice `{self.notices(first)[0].splitlines()[0]}`, and after /reload it comes again")

    def test_another_units_progress_does_not_ask_the_first_unit_again(self):
        # check/causes/spam-1/report.md, OnePerChange: the notice asks MP-1001 for its verify; the coordinator runs
        # MP-1002's anchor and completes MP-1002's todo; nothing changes for MP-1001.
        self.git_repo()
        first = [user_start(), *self.creates(), tool_call("write", "app.py"), edit("app.py"), SETTLE, SETTLED]
        done = todo_state(ONE, {**TWO, "status": "completed"})
        more = [user_start("w2 reported"), bash_result(B_ANCHOR, 0, "5 passed"), {"branchAdd": [done]}, SETTLE]
        notices = self.notices(self.replay([*first, *more], branch=self.branch(), classify=jev_agrees()))
        asked = [notice.splitlines()[0] for notice in notices if A_ANCHOR in notice.splitlines()[0]]
        self.assertLess(len(asked), 2, "nothing changed for MP-1001 between the two turn ends, and both ask it for the same step:\n" + "\n".join(asked))


class TestM7TheNoticeNamesTheUnitThatWaits(MultitaskCase):
    """M7 (OwedIsNamed): when a turn ends with a unit that waits on the coordinator, the notice asks for a step of such a unit."""

    extensions = NOTICE

    def test_the_notice_names_the_unit_that_waits_not_the_first_unit_nobody_started(self):
        # check/causes/owed-2/report.md, OwedIsNamed: MP-1001 waits on MP-1002 (blockedBy) and nobody started it;
        # MP-1002's worker returns and MP-1002 waits on the coordinator.
        self.git_repo()
        one = {**ONE, "status": "pending", "metadata": {**ONE["metadata"], "agents": []}}
        self.replay([user_start(), *self.creates(one, TWO), tool_call("subagent"), spawn("k2", "w2"), SETTLE, SETTLED],
                    branch=self.branch(one, TWO), classify=jev_agrees())
        self.worker_edits(W2)
        notices = self.notices(self.replay([returned("w2"), SETTLE], branch=self.branch(one, TWO), classify=jev_agrees()))
        self.assertTrue(notices, "the turn MP-1002's result started ends with a notice")
        self.assertIn(B_ANCHOR, notices[-1].splitlines()[0],
                      f"MP-1002 waits on the coordinator for its check, MP-1001 waits on MP-1002, and the notice asks: {notices[-1].splitlines()[0]}")


class TestM8TheCoordinatorCanReachClose(MultitaskCase):
    """M8 (CanClose) and M9 (AcceptedCounts): the coordinator can always reach close with evidence."""

    def test_a_handoff_to_a_new_session_keeps_what_the_units_proved(self):
        # check/ends-today/report.md, CanClose and AcceptedCounts: MP-1002's check passed; you hand off to a new session,
        # recreate the todos from the handoff, and declare MP-1002's verify with its task.
        self.start()
        self.worker_edits(W2)
        self.assertIn("verify ✓", self.unit("MP-1002", bash_result(B_ANCHOR, 0, "5 passed")))
        out = self.replay([*self.creates(), stage(stage="verify", note=f"carried over from the handoff: `{B_ANCHOR}` passed", task=2), stage(stage="read")],
                          branch=self.branch(), session="sess-2")
        answer = out["results"][-2]
        after = next(line for line in text_of(out["results"][-1]).splitlines() if line.startswith("MP-1002"))
        if "error" in answer:
            self.assertNotIn("act (missing", after, f"the verify was refused (`{answer['error']}`) and no step but a new change completes MP-1002: {after}")
            return
        self.assertIn("verify ✓", after, f"the tool answered `{text_of(answer)}` to MP-1002's verify in the new session, and the book reads: {after}")

    def test_a_unit_the_coordinator_carried_itself_lands_through_its_car(self):
        # check/without/P8/report.md, Counted and CanClose: the coordinator does MP-1001 itself and pushes its branch as
        # the car; the integrator merges it; sb's landed notice is declared with MP-1001's task, then the observation.
        self.shared_repo()
        one = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "observe": ["export page loads"]}}
        self.replay([*self.creates(one, TWO), spawn("k2", "w2")], branch=self.branch(one, TWO))
        (self.cwd / "app.py").write_text("print(2)\n")
        push = "git checkout -qb agent/mp-1001 && git commit -qam fix && git push -q origin agent/mp-1001"
        self.replay([tool_call("write", "app.py"), edit("app.py"), bash_result(A_ANCHOR, 0, "ok"), bash_call(push), run("git", "checkout", "-qb", "agent/mp-1001"),
                     run("git", "commit", "-qam", "fix"), run("git", "push", "-q", "origin", "agent/mp-1001"), bash_result(push, 0, "")], branch=self.branch(one, TWO))
        train = self.root / "train"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(train)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"], ["merge", "-q", "--no-ff", "-m", "train 1112a", "origin/agent/mp-1001"], ["push", "-q", "origin", "main"]):
            self.sh(*args, where=train)
        sha = self.sh("rev-parse", "HEAD", where=train)
        fetch = "git fetch -q origin"
        after = self.unit("MP-1001", bash_call(fetch), run("git", "fetch", "-q", "origin"), bash_result(fetch, 0, ""),
                          stage(stage="landed", sha=sha, ref="origin/main", task=1), stage(stage="verify", note="export page loads", checkpoint=1, task=1), tasks=(one, TWO))
        self.assertNotIn("(after it lands)", after, f"MP-1001's car {sha[:12]} is in origin/main and its observation was made, and the book reads: {after}")
