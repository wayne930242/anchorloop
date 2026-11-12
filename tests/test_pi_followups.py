"""Follow-ups of the 2.16.0 review rounds (issue #17): the moved-book notice on any tool result, tasks carried into an adopted book,
the forms of `git push` a car is read from, and a finished child whose result is still on its way."""

import os
import time
import unittest
from pathlib import Path

from tests import test_pi_coordinator as coordinator
from tests.pi_harness import SETTLE, bash_call, bash_result, run, stage, todo_create, todo_state, todo_update, tool_result
from tests.test_pi_book import BookCase, edit, text_of
from tests.test_pi_coordinator import CoordinatorCase, done_loop, spawn


class HandoffCase(BookCase):
    """Sessions that hand a book over, as in TestHandoff."""

    def as_session(self, name: str) -> None:
        self.session_file = self.session_file.parent / f"{name}.jsonl"
        self.session_file.write_text("{}\n")

    def book_id(self, session: str = "sess-1") -> str:
        (path,) = [p for p in self.book_files() if p.stem == session]
        return self.book(path)[0]["id"]


class TestMovedNotice(HandoffCase):
    """R2-F003: a session whose book another session resumed is told on the next tool result, whichever tool it is."""

    def moved_session(self) -> tuple:
        self.replay([*self.open_loop(), stage(stage="friction", tried="a", found="b")])
        first, own = self.book_id(), self.session_file
        self.as_session("sess-2")
        self.replay([stage(stage="kind", resume=first)], session="sess-2")
        new = self.session_file
        self.session_file = own
        return first, new

    def test_the_next_bash_result_carries_the_notice_once_and_keeps_its_output(self):
        first, new = self.moved_session()
        out = self.replay([bash_result("ls", 0, "app.py"), bash_result("ls", 0, "app.py")])
        told, quiet = out["results"]
        self.assertIsNotNone(told, "a bash result of the old session was passed without a word")
        self.assertIn("app.py", text_of(told))
        self.assertIn(f"was resumed by session {new}", text_of(told))
        self.assertEqual(told["structuredContent"], {"exit_code": 0, "output": "app.py"})
        self.assertIsNone(quiet, "the notice was told twice")

    def test_an_edit_a_todo_update_and_a_subagent_result_are_told_too(self):
        for step in (edit("src/app.py"), todo_update(1, "write the fix", "completed"), tool_result("subagent", {}, "started", details={"id": "kid", "name": "w1"})):
            with self.subTest(tool=step["payload"]["toolName"]):
                self.tearDown()
                self.setUp()
                self.moved_session()
                out = self.replay([step])
                self.assertIn("was resumed by session", text_of(out["results"][0]) if out["results"][0] else "")

    def test_a_session_whose_book_was_not_moved_is_told_nothing(self):
        self.replay(self.open_loop())
        out = self.replay([bash_result("ls", 0, "app.py")])
        self.assertIsNone(out["results"][0])

    def test_a_session_with_no_loop_at_all_is_told_nothing(self):
        out = self.replay([bash_result("ls", 0, "app.py")])
        self.assertIsNone(out["results"][0])

    def test_after_the_notice_the_next_kind_opens_a_new_loop(self):
        self.moved_session()
        self.replay([bash_result("ls", 0, "")])
        out = self.replay([stage(stage="kind", kind="inline", intent="new work")])
        self.assertEqual(text_of(out["results"][0]), "ok")


class TestAdoptedTasks(HandoffCase):
    """R2-F004: the todos a session created before `kind resume=` are in the adopted book, where a child reads them."""

    def test_a_todo_created_before_the_resume_keeps_its_unit_metadata_in_the_adopted_book(self):
        self.replay([*self.open_loop(), stage(stage="friction", tried="a", found="b")])
        first = self.book_id()
        self.as_session("sess-2")
        mine = todo_create("MP-2002 import", 1, "in_progress", anchor="pytest -q tests/test_import.py", observe=["import page loads"])
        self.replay([mine, stage(stage="kind", resume=first)], session="sess-2")
        header, entries = self.book(next(self.books.rglob("sess-2.yml")))
        self.assertEqual(header["id"], first)
        mine_entries = [entry for entry in entries if entry["stage"] == "task" and entry["subject"] == "MP-2002 import"]
        self.assertEqual(len(mine_entries), 1, "the todo created before the resume was lost, or recorded twice")
        self.assertEqual((mine_entries[0]["anchor"], mine_entries[0]["observe"]), ("pytest -q tests/test_import.py", ["import page loads"]))
        later = [entry for entry in entries if entry["stage"] == "task" and entry["id"] == 1][-1]
        self.assertEqual(later["subject"], "MP-2002 import", "the old session's todo of the same id still wins")
        self.assertEqual([entry["stage"] for entry in entries if entry["stage"] == "friction"], ["friction"], "the adopted entries were dropped")

    def test_a_later_todo_create_does_not_record_the_carried_todo_again(self):
        self.replay([*self.open_loop(), stage(stage="friction", tried="a", found="b")])
        first = self.book_id()
        self.as_session("sess-2")
        mine = todo_create("MP-2002 import", 1, "in_progress")
        self.replay([mine, stage(stage="kind", resume=first), mine], session="sess-2")
        entries = self.book(next(self.books.rglob("sess-2.yml")))[1]
        self.assertEqual(len([entry for entry in entries if entry["stage"] == "task" and entry["subject"] == "MP-2002 import"]), 1)


class TestPushForms(CoordinatorCase):
    """R2-F005: a push is read from `git` with quoted option values or a path, and a refspec the command names counts for this checkout."""

    ONE = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": "pytest -q", "observe": ["export page loads"]}}

    def pushes(self, command: str, *effects: dict) -> list[str]:
        """The refs recorded as cars after a bash call whose text is `command` and whose effects are `effects`."""
        one = self.ONE
        self.replay([todo_create(one["subject"], 1, one["status"], **one["metadata"])], branch=[self.state()])
        self.replay([bash_call(command), *effects, bash_result(command, 0, "")], branch=[self.state()])
        return [entry["ref"] for entry in self.entries("push")]

    def state(self) -> dict:
        return todo_state(self.ONE)

    def test_a_push_through_global_options_with_quoted_values_or_a_path_to_git_is_recorded(self):
        # The checkout's own HEAD is pushed under a new name, so only the command text decides whether the call is read as a push.
        forms = [
            "git -c 'credential.helper=!glab auth git-credential' push -q origin",
            "git -c credential.helper= -c 'credential.helper=!glab auth git-credential' push -q origin",
            'git -c "credential.helper=!glab auth git-credential" push -q origin',
            "git --git-dir /x push -q origin",
            'git -C "a b" push -q origin',
            "/usr/bin/git push -q origin",
        ]
        for n, form in enumerate(forms):
            with self.subTest(form=form):
                self.tearDown()
                self.setUp()
                self.shared_repo()
                refs = self.pushes(form, run("git", "push", "-q", "origin", f"HEAD:refs/heads/agent/mp-1001-{n}"))
                self.assertEqual(refs, [f"origin/agent/mp-1001-{n}"], "the push was not read from this command")

    def test_a_stash_push_a_commit_message_and_a_dry_run_are_not_pushes(self):
        for form in ("git stash push -m x", "git commit -m push", "git push --dry-run origin", "git push -n origin", "git push -q --dry-run origin"):
            with self.subTest(form=form):
                self.tearDown()
                self.setUp()
                self.shared_repo()
                refs = self.pushes(form, run("git", "push", "-q", "origin", "HEAD:refs/heads/agent/mp-1001-x"))
                self.assertEqual(refs, [])

    def test_a_branch_the_command_names_is_this_sessions_car_from_a_checkout_on_another_branch(self):
        specs = ["agent/mp-1001-a", "HEAD:refs/heads/agent/mp-1001-b", "agent/mp-1001-c:agent/mp-1001-c", "+agent/mp-1001-d"]
        for n, spec in enumerate(specs):
            with self.subTest(spec=spec):
                self.tearDown()
                self.setUp()
                self.shared_repo()
                branch = f"agent/mp-1001-{'abcd'[n]}"
                other = self.worktree("wt2", branch)
                self.commit_in(other)
                command = f"git -c 'credential.helper=!glab auth git-credential' push -q origin {spec}"
                refs = self.pushes(command, run("git", "push", "-q", "origin", branch, where=str(other)))
                self.assertEqual(refs, [f"origin/{branch}"], "a push naming the branch was not this session's car")

    def test_a_branch_the_command_does_not_name_is_still_not_this_sessions_car(self):
        self.shared_repo()
        other = self.worktree("wt2", "agent/mp-1002")
        self.commit_in(other)
        refs = self.pushes("git push -q origin agent/mp-1001-a", run("git", "push", "-q", "origin", "agent/mp-1002", where=str(other)))
        self.assertEqual(refs, [])


class TestDeliveryGap(CoordinatorCase):
    """R-F003: a finished child exits before its result is delivered, so a gone child written to a moment ago is still out."""

    process_record = coordinator.TestOrphans.process_record
    dead_pid = coordinator.TestOrphans.dead_pid

    def settle_calls(self, age: float | None) -> int:
        self.shared_repo()
        session = self.process_record(self.dead_pid())
        if age is not None:
            Path(session).write_text("{}\n")
            os.utime(session, (time.time() - age, time.time() - age))
        (self.cwd / "app.py").write_text("print(2)\n")
        out = self.replay([*done_loop(self), spawn("kid", "w1", session, cwd=str(self.cwd)), edit("app.py"), bash_result("pytest -q", 0, "1 passed"), SETTLE],
                          extensions=("book.ts", "second-thought.ts"), classify=coordinator.TestTreeReads.JEV)
        return len(out["classifyCalls"])

    def test_a_gone_child_whose_session_was_written_a_moment_ago_keeps_the_turn_end_quiet(self):
        self.assertEqual(self.settle_calls(2), 0, "a child that just finished counted as gone before its result arrived")

    def test_a_gone_child_whose_session_was_last_written_long_ago_does_not(self):
        self.assertEqual(self.settle_calls(120), 1)

    def test_a_gone_child_with_no_session_file_does_not(self):
        self.assertEqual(self.settle_calls(None), 1)


if __name__ == "__main__":
    unittest.main()
