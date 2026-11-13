"""Follow-ups of the 2.16.0 review rounds (issue #17): the moved-book notice on any tool result, tasks carried into an adopted book,
the forms of `git push` a car is read from, and a finished child whose result is still on its way."""

import os
import subprocess
import time
import unittest
from pathlib import Path

from tests import test_pi_coordinator as coordinator
from tests.pi_harness import SETTLE, bash_call, bash_result, run, stage, todo_create, todo_state, todo_update, tool_call, tool_result
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


class TestResumeOrders(HandoffCase):
    """R3-F002: whichever order the new session resumes in, its todos are the adopted book's, and a child binds to its unit by ticket."""

    CHILD = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "mp1001-worker"}

    def old_session(self) -> str:
        self.git_repo()
        old = [todo_create("MP-7001 a", 1, "in_progress", observe=["a"]), todo_create("MP-7002 b", 2, "in_progress", observe=["b"]),
               todo_create("MP-1001 old export", 3, "in_progress", observe=["c"])]
        self.replay([stage(stage="kind", kind="inline", intent="old", anchor="make loop"), *old, stage(stage="friction", tried="a", found="b")])
        return self.book_id()

    def new_todos(self, **first_meta) -> list[dict]:
        return [todo_create("MP-1001 export", 1, "in_progress", anchor="pytest -q tests/test_export.py", observe=["export works"], **first_meta),
                todo_create("MP-1002 other", 2, "in_progress", anchor="make two", observe=["other works"])]

    def child_anchor_after(self, steps: list[dict]) -> list[str]:
        self.as_session("sess-2")
        self.replay([*steps, spawn("kid", "mp1001-worker", cwd=str(self.cwd))], session="sess-2")
        self.replay([tool_call("write", "src/app.py"), edit()], env=self.CHILD)
        child = next(path for path in self.book_files() if "agents" in path.parts)
        return [entry["check"] for entry in self.book(child)[1] if entry["stage"] == "anchor"]

    def adopted_subjects(self) -> list[str]:
        entries = self.book(next(self.books.rglob("sess-2.yml")))[1]
        after = entries[max(i for i, entry in enumerate(entries) if entry["stage"] == "adopt") :]
        return [entry["subject"] for entry in after if entry["stage"] == "task"]

    def test_kind_resume_first_records_the_new_todos_and_the_child_binds_to_the_new_unit(self):
        first = self.old_session()
        anchors = self.child_anchor_after([stage(stage="kind", resume=first), *self.new_todos()])
        self.assertEqual(self.adopted_subjects(), ["MP-1001 export", "MP-1002 other"])
        self.assertEqual(anchors, ["pytest -q tests/test_export.py"])

    def test_a_resume_in_the_first_todo_records_the_new_todos_and_the_child_binds_to_the_new_unit(self):
        first = self.old_session()
        anchors = self.child_anchor_after(self.new_todos(resume=first))
        self.assertEqual(self.adopted_subjects(), ["MP-1001 export", "MP-1002 other"])
        self.assertEqual(anchors, ["pytest -q tests/test_export.py"])

    def test_todos_before_kind_resume_bind_the_child_although_the_old_session_held_the_same_ticket_open(self):
        first = self.old_session()
        anchors = self.child_anchor_after([*self.new_todos(), stage(stage="kind", resume=first)])
        self.assertEqual(self.adopted_subjects(), ["MP-1001 export", "MP-1002 other"])
        self.assertEqual(anchors, ["pytest -q tests/test_export.py"], "the old session's open MP-1001 todo still competed for the child")


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

    def settle_calls(self, age: float | None, accept: dict | None = None) -> int:
        self.shared_repo()
        session = self.process_record(self.dead_pid())
        if age is not None:
            Path(session).write_text("{}\n")
            os.utime(session, (time.time() - age, time.time() - age))
        (self.cwd / "app.py").write_text("print(2)\n")
        link = spawn("kid", "w1", session, cwd=str(self.cwd))
        if accept is not None:
            link["payload"]["input"]["accept"] = accept
        out = self.replay([*done_loop(self), link, edit("app.py"), bash_result("pytest -q", 0, "1 passed"), SETTLE],
                          extensions=("book.ts", "second-thought.ts"), classify=coordinator.TestTreeReads.JEV)
        return len(out["classifyCalls"])

    def test_a_gone_child_whose_session_was_written_a_moment_ago_keeps_the_turn_end_quiet(self):
        self.assertEqual(self.settle_calls(2), 0, "a child that just finished counted as gone before its result arrived")

    def test_a_gone_child_whose_session_was_last_written_long_ago_does_not(self):
        self.assertEqual(self.settle_calls(120), 1)

    def test_a_gone_child_with_no_session_file_does_not(self):
        self.assertEqual(self.settle_calls(None), 1)

    def test_a_dispatch_with_accept_stays_out_while_the_parent_reruns_its_check(self):
        # R3-F003: the host reruns the check after the child exits, up to its timeout (default 600 s), before it delivers the result;
        # issue #18: the child's own run of the check may come after its last session write, so the grace holds two timeouts.
        self.assertEqual(self.settle_calls(120, {"run": "pytest -q"}), 0, "a child whose check the host is still rerunning counted as gone")
        self.tearDown()
        self.setUp()
        self.assertEqual(self.settle_calls(160, {"run": "pytest -q", "timeoutSec": 60}), 1, "the grace ignored the check's own timeout")
        self.tearDown()
        self.setUp()
        self.assertEqual(self.settle_calls(1300, {"run": "pytest -q"}), 1, "the grace outlived two default check timeouts")


if __name__ == "__main__":
    unittest.main()


class TestPushScanCost(unittest.TestCase):
    """R3-F001: reading a bash command for a push stays linear; a long run without whitespace (a minified JSON body) froze pi for seconds."""

    def test_a_long_command_without_whitespace_is_read_in_well_under_a_second(self):
        script = (
            "import { PUSH, pushRefspecs } from './pi/support/pushes.ts';"
            "const body = '{' + Array.from({ length: 6000 }, (_, i) => `\"k${i}\":\"v${i}\"`).join(',') + '}';"
            "const command = `curl -s -d '${body}' https://example.invalid`;"
            "const began = performance.now(); PUSH.test(command); pushRefspecs(command);"
            "console.log(Math.round(performance.now() - began));"
        )
        out = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
                             cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, check=True, timeout=120)
        self.assertLess(int(out.stdout.strip()), 500, f"a {6000 * 12 // 1000} KB command took {out.stdout.strip()} ms to read for a push")
