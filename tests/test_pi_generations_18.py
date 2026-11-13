"""Round 2 of issue #18: every reader that maps a book entry to a todo id knows the todo list the entry was recorded under. A todo
list starts at an `adopt` or a `reset` (a `todo clear`); evidence for a todo of an earlier list belongs to no todo of the current one,
whatever id it reuses: a car pushed for such a todo lands for no unit (R18-F001), a run of it pairs with no run of a later todo
(R18-F002), the notice's memory of it does not silence a later todo (R18-F003), and a child the current list names takes the anchor
the current list gives it (R18-F004)."""

import subprocess
import unittest

from tests.pi_harness import SETTLE, SETTLED, bash_call, bash_result, run, stage, todo_create, todo_state, todo_update, tool_call, user_start
from tests import test_model_multitask as multitask
from tests import test_pi_anchorloop as anchorloop
from tests import test_pi_followups_18 as followups_18
from tests.test_pi_anchorloop import answers
from tests.test_pi_book import edit, text_of
from tests.test_pi_coordinator import spawn
from tests.test_pi_followups_18 import CLEAR, NEW, creates, state

TWO = multitask.TWO

A_ANCHOR = "pytest tests/export"
ONE = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "observe": ["export page loads"]}}
NEW_ONE = {"subject": "MP-9001 import", "status": "in_progress", "metadata": {"anchor": "pytest tests/import", "observe": ["import page loads"]}}
NEW_TWO = {"subject": "MP-9002 report", "status": "in_progress", "metadata": {"anchor": "pytest tests/report", "observe": ["report page loads"]}}
B_ANCHOR = "pytest tests/view"
TWO_SEEN = {"subject": "MP-1002 view", "status": "in_progress", "metadata": {"anchor": B_ANCHOR, "observe": ["view page loads"]}}
TWO_AGAIN = {"subject": "MP-1002 view again", "status": "in_progress", "metadata": {"anchor": B_ANCHOR, "observe": ["view page loads"]}}
AGAIN = {"subject": "MP-1001 export again", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "observe": ["export page loads"]}}
PUSH = "git checkout -qb agent/mp-1001 && git commit -qam fix && git push -q origin agent/mp-1001"
FETCH = "git fetch -q origin"


class TestRetiredCar(multitask.MultitaskCase):
    """R18-F001: the car pushed for a todo of an earlier list lands for no unit of the current list, until the recreated unit of its
    ticket declares it (R3-F002: that unit and no other)."""

    def push_car(self) -> None:
        self.shared_repo()
        self.replay([*self.creates(ONE, TWO), spawn("k2", "w2")], branch=self.branch(ONE, TWO))
        (self.cwd / "app.py").write_text("print(2)\n")
        # The change is committed by bash and recorded by no edit, so only its landing can count as a unit's change.
        self.replay([bash_result(A_ANCHOR, 0, "ok"), bash_call(PUSH), run("git", "checkout", "-qb", "agent/mp-1001"),
                     run("git", "commit", "-qam", "fix"), run("git", "push", "-q", "origin", "agent/mp-1001"), bash_result(PUSH, 0, "")], branch=self.branch(ONE, TWO))
        self.assertEqual([entry.get("task") for entry in self.entries("push")], [1], "the car was not pushed for MP-1001")

    def merge_train(self) -> str:
        train = self.root / "train"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(train)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"], ["merge", "-q", "--no-ff", "-m", "train", "origin/agent/mp-1001"], ["push", "-q", "origin", "main"]):
            self.sh(*args, where=train)
        return self.sh("rev-parse", "HEAD", where=train)

    def fetch(self) -> list[dict]:
        return [bash_call(FETCH), run("git", "fetch", "-q", "origin"), bash_result(FETCH, 0, "")]

    def test_a_landing_after_the_clear_counts_for_no_unit(self):
        self.push_car()
        self.replay([CLEAR, *self.creates(NEW_ONE, NEW_TWO)], branch=self.branch(NEW_ONE, NEW_TWO))
        sha = self.merge_train()
        out = self.replay([*self.fetch(), stage(stage="landed", sha=sha, ref="origin/main"), bash_result("pytest tests/import", 0, "ok"), stage(stage="verify", note="import page loads", checkpoint=1, task=1), stage(stage="read")], branch=self.branch(NEW_ONE, NEW_TWO))
        (land,) = [entry for entry in self.entries("land") if entry.get("verified") and entry.get("head")]
        self.assertTrue(land.get("retired"), f"the landing of the retired todo's car was not marked retired: {land}")
        lines = text_of(out["results"][-1]).splitlines()
        line = next(line for line in lines if line.startswith("MP-9001"))
        self.assertIn("(after it lands)", line, f"MP-9001's observation was taken against the retired todo's car: {line}")

    def test_a_landing_before_the_clear_does_not_keep_the_recreated_unit_from_declaring_it(self):
        self.push_car()
        sha = self.merge_train()
        self.replay([*self.fetch(), stage(stage="landed", sha=sha, ref="origin/main", task=1)], branch=self.branch(ONE, TWO))
        self.assertEqual([entry.get("task") for entry in self.entries("land")], [1], self.entries("land"))
        after = self.unit("MP-1001", CLEAR, *self.creates(AGAIN, TWO), stage(stage="landed", sha=sha, ref="origin/main", task=1),
                          bash_result(A_ANCHOR, 0, "ok"), stage(stage="verify", note="export page loads", checkpoint=1, task=1), tasks=(AGAIN, TWO))
        self.assertNotIn("(after it lands)", after, f"the recreated MP-1001 could not declare its car {sha[:12]}: {after}")

    def push(self, ticket: str, name: str) -> list[dict]:
        """The steps that push `name` as the car `agent/<ticket>`, cut from main."""
        branch = f"agent/{ticket}"
        command = f"git checkout -q main && git checkout -qb {branch} && git add {name} && git commit -qm fix && git push -q origin {branch}"
        return [bash_call(command), run("git", "checkout", "-q", "main"), run("git", "checkout", "-qb", branch), run("sh", "-c", f"echo x > {name}"), run("git", "add", name),
                run("git", "commit", "-qm", "fix"), run("git", "push", "-q", "origin", branch), bash_result(command, 0, "")]

    def merge_cars(self, *tickets: str) -> str:
        train = self.root / "train"
        subprocess.run(["git", "clone", "-q", str(self.root / "remote.git"), str(train)], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"], *(["merge", "-q", "--no-ff", "-m", "train", f"origin/agent/{ticket}"] for ticket in tickets), ["push", "-q", "origin", "main"]):
            self.sh(*args, where=train)
        return self.sh("rev-parse", "HEAD", where=train)

    def taken(self) -> dict[str, list]:
        """Each car's landings by the unit they were recorded for (None: for no unit)."""
        found: dict[str, list] = {}
        for entry in self.entries("land"):
            if entry.get("verified") and entry.get("pushed"):
                found.setdefault(entry["pushed"], []).append(entry.get("task"))
        return found

    def test_each_recreated_unit_declares_its_own_car_and_only_that(self):
        self.shared_repo()
        old, new = (ONE, TWO_SEEN), (AGAIN, TWO_AGAIN)
        # The linked worker makes the session watch origin/main, as in `push_car`.
        self.replay([*self.creates(*old), spawn("k2", "w2"), *self.push("mp-1001", "one.py"), *self.push("mp-1002", "two.py")], branch=self.branch(*old))
        self.assertEqual([entry.get("task") for entry in self.entries("push")], [1, 2], "each car was not pushed for its own unit")
        self.replay([CLEAR, *self.creates(*new)], branch=self.branch(*new))
        sha = self.merge_cars("mp-1001", "mp-1002")
        out = self.replay([*self.fetch(), stage(stage="landed", sha=sha, ref="origin/main", task=1)], branch=self.branch(*new))
        self.assertEqual(self.taken(), {"origin/agent/mp-1001": [None, 1], "origin/agent/mp-1002": [None]}, f"MP-1001's declaration took a car that is not its own: {text_of(out['results'][-1])}")
        out = self.replay([stage(stage="landed", sha=sha, ref="origin/main", task=2), bash_result(B_ANCHOR, 0, "ok"), stage(stage="verify", note="view page loads", checkpoint=1, task=2),
                           stage(stage="landed", sha=sha, ref="origin/main", task=2), stage(stage="read")], branch=self.branch(*new))
        self.assertEqual(self.taken(), {"origin/agent/mp-1001": [None, 1], "origin/agent/mp-1002": [None, 2]})
        read = text_of(out["results"][-1])
        after = next(line for line in read.splitlines() if line.startswith("MP-1002"))
        self.assertNotIn("(after it lands)", after, f"the recreated MP-1002 could not declare its own car: {after}")
        # A car recorded for no unit and then for its own unit is one landing to the reader.
        for text in (read, text_of(out["results"][-2])):
            self.assertEqual([text.count(f"origin/agent/{ticket} ") for ticket in ("mp-1001", "mp-1002")], [1, 1], text)

    def test_a_unit_of_another_ticket_cannot_declare_the_retired_car(self):
        self.push_car()
        new = (NEW_ONE, NEW_TWO)
        self.replay([CLEAR, *self.creates(*new)], branch=self.branch(*new))
        sha = self.merge_train()
        steps = [*self.fetch(), stage(stage="landed", sha=sha, ref="origin/main", task=2), bash_result("pytest tests/report", 0, "ok"),
                 stage(stage="verify", note="report page loads", checkpoint=1, task=2), stage(stage="read")]
        out = self.replay(steps, branch=self.branch(*new))
        self.assertEqual(self.taken(), {"origin/agent/mp-1001": [None]}, "MP-9002 took the car of MP-1001")
        declared = text_of(out["results"][next(i for i, step in enumerate(steps) if step.get("params", {}).get("stage") == "landed")])
        self.assertIn("names another ticket", declared, "the reply does not say why the car was left")
        after = next(line for line in text_of(out["results"][-1]).splitlines() if line.startswith("MP-9002"))
        self.assertIn("(after it lands)", after, f"MP-9002's observation was taken against MP-1001's car: {after}")


class TestRetryAcrossLists(followups_18.TestReusedTodoIds):
    """R18-F002: a failure of the new todo #1 before its first pass is red-first work, not a rerun of the old todo #1."""

    def test_red_first_work_of_a_reused_id_is_no_rerun(self):
        self.old_session()
        self.replay([CLEAR, *creates(NEW), bash_result("make c", 1, "FAILED test_c"), bash_result("make c", 0, "ok")], branch=[state(NEW)])
        self.assertEqual([entry for entry in self.entries("friction") if entry.get("auto")], [], "red-first work of the new #1 was taken for a rerun")

    def test_a_rerun_within_one_list_is_still_friction(self):
        self.old_session()
        self.replay([CLEAR, *creates(NEW), bash_result("make c", 0, "ok"), bash_result("make c", 1, "FAILED test_c"), bash_result("make c", 0, "ok")], branch=[state(NEW)])
        self.assertEqual(len([entry for entry in self.entries("friction") if entry.get("auto")]), 1)


for name in [name for name in vars(followups_18.TestReusedTodoIds) if name.startswith("test_")]:
    setattr(TestRetryAcrossLists, name, None)


class TestNoticeAcrossLists(anchorloop.TestSecondThought):
    """R18-F003: the notice remembers open todo ids of the list it judged; a new todo that reuses an id after a clear is judged."""

    def test_a_new_open_todo_after_a_clear_is_judged_though_its_id_was_open_before(self):
        old = {"branchAdd": [todo_state({"subject": "port the cache", "status": "pending"})]}
        new = {"branchAdd": [todo_state({"subject": "write the docs", "status": "pending"})]}
        out = self.replay([*self.loop(), old, SETTLE, SETTLED, CLEAR, todo_create("write the docs", 1, "pending"), new, SETTLE], classify=answers())
        self.assertEqual(len(out["classifyCalls"]), 2, "the new todo #1 was taken for the old open todo #1 and not judged")


class TestUnitNoticeAcrossLists(multitask.MultitaskCase):
    """R18-F003: a unit of a new list is judged though the unit of the old list with its id was last judged at the same step."""

    extensions = multitask.NOTICE

    def test_a_new_unit_that_reuses_an_id_is_judged(self):
        old = (multitask.ONE, multitask.TWO)
        new = ({**multitask.ONE, "subject": "MP-9001 import"}, {**multitask.TWO, "subject": "MP-9002 report"})
        self.git_repo()
        first = self.replay([user_start(), *self.creates(*old), tool_call("write", "app.py"), edit("app.py"), SETTLE, SETTLED], branch=self.branch(*old), classify=multitask.jev_agrees())
        self.assertEqual(len(first["classifyCalls"]), 1, "the old unit was not judged")
        out = self.replay([user_start(), CLEAR, *self.creates(*new), SETTLE], branch=self.branch(*new), classify=multitask.jev_agrees())
        self.assertEqual(len(out["classifyCalls"]), 1, "the new unit #1 was taken for the old unit #1 and not judged")


for name in [name for name in vars(anchorloop.TestSecondThought) if name.startswith("test_")]:
    setattr(TestNoticeAcrossLists, name, None)


class TestNamedChildAcrossAdopt(followups_18.TestInFlightChildAcrossAdopt):
    """R18-F004: a child the current list names, in any status or as its only unit, takes what the current list gives it."""

    def test_a_single_new_unit_that_names_the_child_wins_over_the_old_unit(self):
        renewed = (("MP-7001 a again", "make a2"),)
        self.assertEqual(self.child_anchor(creates(renewed), [state(renewed)]), ["make loop"])

    def test_a_completed_new_todo_that_names_the_child_wins_over_the_old_unit(self):
        renewed = (("MP-7001 a again", "make a2"), ("MP-9001 c", "make c"), ("MP-9002 d", "make d"))
        steps = [*creates(renewed), todo_update(1, "MP-7001 a again", "completed", anchor="make a2", kind="inline")]
        branch = [todo_state({"subject": "MP-7001 a again", "status": "completed", "metadata": {"anchor": "make a2", "kind": "inline"}},
                             *({"subject": s, "status": "in_progress", "metadata": {"anchor": a, "kind": "inline"}} for s, a in renewed[1:]))]
        self.assertEqual(self.child_anchor(steps, branch), ["make loop"], "the old unit's anchor overrode the todo the current list names the child by")


for name in [name for name in vars(followups_18.TestInFlightChildAcrossAdopt) if name.startswith("test_")]:
    setattr(TestNamedChildAcrossAdopt, name, None)


if __name__ == "__main__":
    unittest.main()
