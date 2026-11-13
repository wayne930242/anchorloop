"""Follow-ups of the 2.16.2 review (issue #18): evidence tied to a todo id belongs to that todo and not to a later todo that reuses
the id, a dispatch with `accept` waits for the child's own check and the host's rerun, and a child still out when its parent's book
is adopted keeps the anchor of the unit it was dispatched for."""

import unittest

from tests.pi_harness import bash_result, stage, todo_create, todo_state, tool_call, tool_result
from tests.test_pi_book import edit
from tests.test_pi_coordinator import spawn
from tests import test_pi_followups as followups
from tests.test_pi_followups import HandoffCase

OLD = (("MP-7001 a", "make a"), ("MP-7002 b", "make b"))
NEW = (("MP-9001 c", "make c"), ("MP-9002 d", "make d"))


def creates(todos: tuple) -> list[dict]:
    return [todo_create(subject, i + 1, "in_progress", anchor=anchor, kind="inline") for i, (subject, anchor) in enumerate(todos)]


def state(todos: tuple) -> dict:
    return todo_state(*({"subject": subject, "status": "in_progress", "metadata": {"anchor": anchor, "kind": "inline"}} for subject, anchor in todos))


CLEAR = tool_result("todo", {"action": "clear"}, "cleared", details={"tasks": [], "nextId": 1})


class TestReusedTodoIds(HandoffCase):
    """P2: a passing run of the old todo #1's anchor is no evidence for a new todo #1 created after an adopt or a `todo clear`."""

    def old_session(self) -> None:
        self.git_repo()
        steps = [stage(stage="kind", kind="inline", intent="old", anchor="make loop"), *creates(OLD), tool_call("write", "app.py"), edit("app.py"), bash_result("make a", 0, "ok")]
        self.replay(steps, branch=[state(OLD)])
        lines = self.read_text([], branch=[state(OLD)]).splitlines()
        self.assertIn("#1 in_progress MP-7001 a — make a (exit 0)", lines, "the old todo's own run was not recorded")

    def assert_new_units_have_no_run(self, lines: list[str]) -> None:
        self.assertIn("MP-9001 inline · act ✓ → verify (missing: a passing run of `make c` after the last change)", lines,
                      "the new todo #1 took the old todo #1's run as its verify")
        self.assertIn("#1 in_progress MP-9001 c — make c", lines, "the new todo #1's line shows the old todo #1's exit")

    def test_a_todo_that_reuses_an_id_after_an_adopt_does_not_inherit_the_old_todos_run(self):
        self.old_session()
        first = self.book_id()
        self.as_session("sess-2")
        lines = self.read_text([stage(stage="kind", resume=first), *creates(NEW)], session="sess-2", branch=[state(NEW)]).splitlines()
        self.assert_new_units_have_no_run(lines)

    def test_a_todo_that_reuses_an_id_after_a_todo_clear_does_not_inherit_the_old_todos_run(self):
        self.old_session()
        lines = self.read_text([CLEAR, *creates(NEW)], branch=[state(NEW)]).splitlines()
        self.assert_new_units_have_no_run(lines)
        subjects = [entry["subject"] for entry in self.entries("task")]
        self.assertEqual(subjects[-2:], ["MP-9001 c", "MP-9002 d"], "the todos created after the clear were not recorded")

    def test_a_run_after_the_clear_counts_for_the_new_todo(self):
        self.old_session()
        lines = self.read_text([CLEAR, *creates(NEW), bash_result("make c", 0, "ok")], branch=[state(NEW)]).splitlines()
        self.assertIn("#1 in_progress MP-9001 c — make c (exit 0)", lines)
        self.assertTrue(any(line.startswith("MP-9001 inline · verify ✓") for line in lines), lines)


class TestAcceptGrace(followups.TestDeliveryGap):
    """P3: the child runs its own check before it exits and the host reruns it after, so the grace holds two check timeouts."""

    def test_a_check_slower_than_half_its_timeout_is_still_on_its_way(self):
        self.assertEqual(self.settle_calls(120, {"run": "pytest -q", "timeoutSec": 60}), 0, "the grace held one check timeout, not the child's run and the host's rerun")

    def test_past_two_check_timeouts_the_child_is_gone(self):
        self.assertEqual(self.settle_calls(160, {"run": "pytest -q", "timeoutSec": 60}), 1)


# Only the tests above run from the class it extends.
for name in [name for name in vars(followups.TestDeliveryGap) if name.startswith("test_")]:
    setattr(TestAcceptGrace, name, None)


class TestInFlightChildAcrossAdopt(HandoffCase):
    """P3: a child the old session dispatched for a unit keeps that unit's anchor after the new session adopts the book."""

    CHILD = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "mp7001-worker"}

    def child_anchor(self, new_steps: list[dict], branch: list) -> list[str]:
        self.git_repo()
        self.replay([stage(stage="kind", kind="inline", intent="old", anchor="make loop"), *creates(OLD), spawn("kid", "mp7001-worker", cwd=str(self.cwd))], branch=[state(OLD)])
        first = self.book_id()
        self.as_session("sess-2")
        self.replay([stage(stage="kind", resume=first), *new_steps], session="sess-2", branch=branch)
        self.replay([tool_call("write", "app.py"), edit("app.py")], env=self.CHILD)
        child = next(path for path in self.book_files() if "agents" in path.parts)
        return [entry["check"] for entry in self.book(child)[1] if entry["stage"] == "anchor"]

    def test_before_the_new_session_recreates_its_todos_the_child_keeps_its_units_anchor(self):
        self.assertEqual(self.child_anchor([], []), ["make a"])

    def test_new_units_that_do_not_name_the_child_leave_it_its_old_units_anchor(self):
        self.assertEqual(self.child_anchor(creates(NEW), [state(NEW)]), ["make a"])

    def test_a_new_unit_that_names_the_child_wins(self):
        renewed = (("MP-7001 a again", "make a2"), ("MP-9002 d", "make d"))
        self.assertEqual(self.child_anchor(creates(renewed), [state(renewed)]), ["make a2"])


if __name__ == "__main__":
    unittest.main()
