"""Replays of the bug paths of the loop book model (docs/models/loop-book): each test walks one path of a check report
on the real extensions and asserts the rule at its end, in the reader's words.

The model found each path on the code at 230605a, where every test here was red; the boss decided the rules on issues #2 to
#8 (2026-11-12), and the code since 2.16.0 holds them. Rule 3 is narrowed by the decision on #4: only a reviewer's verdict is
a review round. A step a fix may refuse is an attempt, and its refusal passes.
"""

import subprocess
from pathlib import Path

from tests.pi_harness import SETTLE, SETTLED, bash_call, bash_result, run, stage, todo_create, todo_state, tool_call, user_start
from tests.test_pi_book import edit, subagent_result, text_of
from tests.test_pi_coordinator import CoordinatorCase, returned, spawn

ANCHOR = "pytest -q"
CHILD = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w1"}
CLEAR = "Reviewed the diff.\nBlocking: P0=0 P1=0"


def jev_agrees() -> dict:
    """Jev's answer when it has nothing against the book's reading: advance, intent met, no review owed, acceptable."""
    return {"stopReason": "stop", "answers": {
        "move": {"type": "choice", "choice": "advance", "probabilities": {"advance": 0.9}},
        "done": {"type": "bool", "probability": 0.9},
        "review": {"type": "choice", "choice": "none", "probabilities": {"none": 0.9}},
        "quality": {"type": "score", "score": 2.5},
    }}


class ModelCase(CoordinatorCase):
    extensions = ("book.ts",)

    def opening(self, kind: str = "inline", **extra) -> list[dict]:
        return [stage(stage="kind", kind=kind, intent="fix the export", anchor=ANCHOR, **extra), todo_create()]

    def change(self, path: str = "app.py") -> list[dict]:
        """You change the code: a write the book sees from its call to its result."""
        return [tool_call("write", path), edit(path)]

    def passes(self) -> dict:
        return bash_result(ANCHOR, 0, "5 passed")

    def line(self, *steps: dict, **kwargs) -> str:
        """The book's phase line after `steps`."""
        return text_of(self.replay([*steps, stage(stage="read")], **kwargs)["results"][-1]).splitlines()[0]

    def second_repo(self) -> Path:
        other = self.root / "other-repo"
        other.mkdir()
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            self.sh(*args, where=other)
        (other / "lib.py").write_text("x = 1\n")
        self.sh("add", "lib.py", where=other)
        self.sh("commit", "-qm", "base", where=other)
        return other


class TestRule1ACheckThatPassedStaysPassed(ModelCase):
    """Rule 1 (KeptDone): a check that passed stays passed until something the anchor tests changes, or you take it back."""

    def checked(self, kind: str = "inline", *more: dict) -> str:
        return self.line(*self.opening(kind), *self.change(), self.passes(), *more)

    def test_a_file_written_in_another_repository_does_not_undo_the_check(self):
        # check/full/report.md, KeptDone: the anchor passes, then you write a file in another repository.
        self.git_repo()
        other = self.second_repo()
        self.assertEqual(self.checked(), "inline · phase verify ✓ → close")
        after = self.line(*self.change(str(other / "lib.py")))
        self.assertEqual(after, "inline · phase verify ✓ → close",
                         f"the anchor `{ANCHOR}` passed in this checkout and nothing in this checkout changed, yet after a write to {other.name}/lib.py the book reads: {after}")

    def test_a_note_git_ignores_does_not_undo_the_check_or_the_review(self):
        # check/causes/kept-1/report.md: the anchor passes, then you write a note git ignores.
        self.git_repo()
        (self.cwd / ".gitignore").write_text("notes/\n")
        self.sh("add", ".gitignore")
        self.sh("commit", "-qm", "ignore notes")
        self.assertEqual(self.checked("reviewed", subagent_result("reviewer", "r1", CLEAR)), "reviewed · phase review ✓ → close")
        after = self.line(*self.change("notes/handoff.md"))
        self.assertEqual(after, "reviewed · phase review ✓ → close",
                         f"the check passed and the review was clear; a note under an ignored folder is in no diff, yet after it the book reads: {after}")

    def test_a_workers_edit_in_its_own_worktree_does_not_undo_the_check_of_this_checkout(self):
        # check/causes/kept-2/report.md: the anchor passes, you start a worker, the worker edits in its own worktree.
        self.shared_repo()
        tree = self.worktree()
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": self.sh("rev-parse", "HEAD")}
        self.assertEqual(self.checked("inline", spawn("kid", "w1", "/s/kid.jsonl", worktree=worktree)), "inline · phase verify ✓ → close")
        main, self.cwd = self.cwd, tree
        try:
            self.replay(self.change(), env=CHILD)
        finally:
            self.cwd = main
        after = self.line()
        self.assertEqual(after, "inline · phase verify ✓ → close",
                         f"the worker edited {tree.name}/app.py, a tree this checkout's `{ANCHOR}` does not run on, yet the book asks this checkout to run it again: {after}")


class TestRule2AVerifyTheToolAcceptedCounts(ModelCase):
    """Rule 2 (AcceptedCounts): a verify the tool answered ok to counts; the book does not ask for it again before the next change."""

    ONE = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": "pytest tests/export", "agents": ["w1"]}}
    TWO = {"subject": "MP-1002 view", "status": "in_progress", "metadata": {"anchor": "pytest tests/view", "agents": ["w2"]}}

    def test_a_declared_verify_without_a_task_is_not_answered_ok_and_then_asked_for_again(self):
        # check/units/report.md, AcceptedCounts: two units with their own anchors; you declare a passing verify with no task.
        self.git_repo()
        branch = [todo_state(self.ONE, self.TWO)]
        creates = [todo_create(task["subject"], i + 1, task["status"], **task["metadata"]) for i, task in enumerate((self.ONE, self.TWO))]
        out = self.replay([*creates, *self.change(), stage(stage="verify", note="ran both suites: 40 passed"), stage(stage="read")], branch=branch)
        answer, read = out["results"][-2], text_of(out["results"][-1])
        if "error" in answer:
            return  # A fix may refuse the declaration and ask for `task`; then nothing was accepted.
        asked = [line for line in read.splitlines() if line.startswith("MP-100") and "→ verify (missing: a passing run of" in line]
        self.assertLess(len(asked), 2, f"the tool answered `{text_of(answer)}` to the verify, and the book still asks every unit for it:\n" + "\n".join(asked))


class TestRule3AReviewThatCameBackClearCounts(ModelCase):
    """Rule 3 (ReportedReviewCounts), narrowed by the decision on issue #4 (2026-11-12): a review that came back Blocking P0=0 P1=0
    after the last change counts as the review when a reviewer (`reviewer`, `adversarial-reviewer`) reported it."""

    def test_a_clear_report_from_a_subagent_of_another_role_is_not_a_review(self):
        # check/full/report.md, ReportedReviewCounts: you ask a subagent whose role is not reviewer; it reports no blocking finding.
        # Issue #4 decided that only a reviewer's verdict counts, so the book still asks for the review.
        self.git_repo()
        after = self.line(*self.opening("reviewed"), *self.change(), self.passes(), subagent_result("worker", "review-1", CLEAR))
        self.assertEqual(after, "reviewed · phase verify ✓ → review (missing: a review round after the last change with Blocking: P0=0 P1=0)",
                         f"a worker reported `Blocking: P0=0 P1=0`; only a reviewer's verdict is a review round, yet the book reads: {after}")

    def test_a_clear_review_counts_in_a_session_that_is_itself_a_subagent(self):
        # check/subsession/report.md, ReportedReviewCounts and CanFinish: a worker's own reviewer returns; the result is not read.
        self.git_repo()
        after = self.line(*self.opening("reviewed"), *self.change(), self.passes(), subagent_result("reviewer", "r1", CLEAR), env=CHILD)
        self.assertEqual(after, "reviewed · phase review ✓ → close",
                         f"a worker's reviewed loop got `Blocking: P0=0 P1=0` from its reviewer; nothing but `skip` can complete its review, and the book reads: {after}")


class TestRule4ALoopCanBeFinishedWithEvidence(ModelCase):
    """Rule 4 (CanFinish): while a phase is missing, somebody has a step that supplies its evidence (`skip` is not evidence)."""

    OBSERVE = "health returns 200"

    def every_route(self) -> tuple[list[str], str]:
        """You push, tell the book it landed, declare the observation seen, and run the anchor again: each answer, then the phase line."""
        (self.cwd / "app.py").write_text("print(2)\n")
        push = "git commit -qam fix && git push -q origin main"
        self.replay([bash_call(push), run("git", "commit", "-qam", "fix"), run("git", "push", "-q", "origin", "main"), bash_result(push, 0, "")])
        out = self.replay([stage(stage="landed", ref="origin/main", sha=self.sh("rev-parse", "HEAD")), stage(stage="verify", note="GET /health 200", checkpoint=1),
                           self.passes(), stage(stage="read")])
        answers = [result["error"] if "error" in result else text_of(result) for result in out["results"][:2]]
        return answers, text_of(out["results"][-1]).splitlines()[0]

    def test_an_observation_can_be_closed_in_a_session_that_started_no_subagent(self):
        # check/inline/report.md, CanFinish: you list an observation, change the code, the anchor passes; no ref is watched.
        self.shared_repo()
        self.replay([*self.opening(observe=[self.OBSERVE]), *self.change(), self.passes()])
        answers, after = self.every_route()
        self.assertNotIn("(after it lands)", after,
                         f"the commit is on origin/main and the observation was made, yet no step records the landing (landed: `{answers[0]}`; checkpoint: `{answers[1]}`) and the book reads: {after}")

    def test_following_the_checkpoint_refusal_does_not_leave_verify_out_of_reach(self):
        # The same end by the tool's own advice: a todo lists the observation, the checkpoint without `task` is refused with
        # "give `observe` on the kind call", and following that undoes a verify that was done.
        self.shared_repo()
        tasks = ({"subject": "ship the fix", "status": "in_progress", "metadata": {"anchor": ANCHOR}},
                 {"subject": "watch production", "status": "pending", "metadata": {"observe": [self.OBSERVE]}})
        branch = [todo_state(*tasks)]
        steps = [todo_create("ship the fix", 1, "in_progress", anchor=ANCHOR), todo_create("watch production", 2, observe=[self.OBSERVE]), *self.change(), self.passes()]
        self.assertEqual(text_of(self.replay([*steps, stage(stage="read")], branch=branch)["results"][-1]).splitlines()[0], "inline · phase verify ✓ → close")
        refused = self.replay([stage(stage="verify", note="GET /health 200", checkpoint=1)], branch=branch)["results"][0]
        if "error" not in refused or "kind call" not in refused["error"]:
            return  # A fix may accept the checkpoint or name another way; the advice that led here is gone.
        self.replay([stage(stage="kind", observe=[self.OBSERVE])], branch=branch)
        answers, after = self.every_route()
        self.assertNotIn("(after it lands)", after,
                         f"the refusal said `{refused['error']}`; after doing that, no step completes verify again (landed: `{answers[0]}`) and the book reads: {after}")


class TestRule5TheNoticeWaitsForTheSubagents(ModelCase):
    """Rule 5 (QuietWhileWaiting): while a subagent the loop started has not returned, the turn-end notice does not judge the loop."""

    extensions = ("book.ts", "second-thought.ts")

    def judged(self, out: dict) -> str:
        """What the last turn end did, in words; empty when it stayed quiet."""
        last = out["results"][-1] or {}
        notices = [entry["content"] for entry in last.get("entries", []) if entry["type"] == "custom_message"]
        parts = [f"Jev was asked {len(out['classifyCalls'])} time(s)"] if out["classifyCalls"] else []
        return "; ".join([*parts, *(f"the agent was told `{notice}`" for notice in notices), *(["the run was continued"] if last.get("continue") else [])])

    def test_a_turn_someone_else_started_is_not_judged_while_the_worker_is_out(self):
        # check/full/report.md, QuietWhileWaiting: you change the code, start a worker and wait; your turn ends with no notice;
        # someone speaks to you; your turn ends again.
        self.git_repo()
        out = self.replay([user_start(), *self.opening(), *self.change(), tool_call("subagent"), spawn("kid", "w1"), SETTLE, SETTLED,
                           user_start("how is it going?"), SETTLE], classify=jev_agrees())
        self.assertEqual(self.judged(out), "", "worker w1 has not returned, and at the end of a turn the user started: " + self.judged(out))

    def test_a_turn_one_subagent_started_is_not_judged_while_another_is_out(self):
        # check/causes/quiet-1/report.md: nobody else speaks; two subagents are out and the first to return starts the turn.
        self.git_repo()
        out = self.replay([user_start(), *self.opening(), *self.change(), tool_call("subagent"), spawn("k1", "w1"), spawn("k2", "w2"), SETTLE, SETTLED,
                           returned("w1"), SETTLE], classify=jev_agrees())
        self.assertEqual(self.judged(out), "", "worker w2 has not returned, and at the end of the turn w1's result started: " + self.judged(out))


class TestRule6NoCheckPassesForCodeThatChangedAfterIt(ModelCase):
    """Rule 6 (NoStalePass): the book never shows the check as passed for code that changed after it ran."""

    def test_a_change_made_through_a_shell_command_undoes_the_check(self):
        # check/full/report.md, NoStalePass: the anchor passes, then you change the code through a shell command.
        self.git_repo()
        self.assertEqual(self.line(*self.opening(), *self.change(), self.passes()), "inline · phase verify ✓ → close")
        command = "sed -i.bak 's/print(1)/print(2)/' app.py"
        after = self.line(bash_call(command), run("sh", "-c", "printf 'print(2)\\n' > app.py"), bash_result(command, 0, ""))
        self.assertEqual(subprocess.run(["git", "-C", str(self.cwd), "diff", "--name-only"], capture_output=True, text=True).stdout.strip(), "app.py")
        self.assertNotIn("verify ✓", after, f"app.py changed after `{ANCHOR}` last ran, and the book still reads: {after}")


class TestRule7TheReviewReadTheChange(ModelCase):
    """Rule 7 (ReviewReadTheChange): the book never shows a review as clear when the code changed while the reviewer was reading."""

    def test_a_review_that_started_before_the_last_change_does_not_cover_it(self):
        # check/small/report.md, ReviewReadTheChange: you change the code, start a reviewer, change the code again, and the
        # review comes back clear. The replay adds the two anchor runs the model's shortest path leaves out.
        self.git_repo()
        reviewer = spawn("rev", "r1")
        reviewer["payload"]["details"]["agent"] = "reviewer"
        after = self.line(*self.opening("reviewed"), *self.change(), self.passes(), tool_call("subagent"), reviewer,
                          *self.change(), self.passes(), subagent_result("reviewer", "r1", CLEAR))
        self.assertNotIn("review ✓", after, f"the reviewer started reading before the last change to app.py, and the book takes its verdict for that change: {after}")
