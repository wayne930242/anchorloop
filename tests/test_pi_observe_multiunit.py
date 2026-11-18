"""A loop-level observe item (from `kind observe` or the first todo's metadata) can be ticked or dropped in a book of several units.

Before 2.16.9 a `verify checkpoint N` without `task` was refused as soon as the book held two units, a checkpoint with `task` read only
that unit's own list, and `kind observe: []` changed nothing, so an item that was done could never be recorded and every unit kept
reporting it as missing.
"""

from tests.pi_harness import bash_call, bash_result, run, stage, todo_state, tool_call
from tests.test_model_multitask import MultitaskCase
from tests.test_pi_book import edit, text_of

A_ANCHOR, B_ANCHOR = "pytest tests/export", "pytest tests/view"
OBSERVE = "mp-infra MR !2 pipeline"
OWN = "export page loads"
ONE = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "kind": "inline"}}
TWO = {"subject": "MP-1002 view", "status": "in_progress", "metadata": {"anchor": B_ANCHOR, "kind": "inline"}}
ONE_OWN = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "kind": "inline", "observe": [OWN]}}
MISSING = "missing: observe"


class LoopObserveCase(MultitaskCase):
    """Two units and a loop-level observe item; both units have landed and passed their anchors."""

    UNITS: tuple[dict, ...] = (ONE, TWO)

    def start(self) -> None:  # type: ignore[override]
        self.shared_repo()
        self.replay([*self.creates(*self.UNITS), stage(stage="kind", observe=[OBSERVE])], branch=self.branch(*self.UNITS))
        (self.cwd / "app.py").write_text("print(2)\n")
        push = "git commit -qam fix && git push -q origin main"
        self.replay([tool_call("write", "app.py"), edit("app.py"), bash_call(push), run("git", "commit", "-qam", "fix"), run("git", "push", "-q", "origin", "main"),
                     bash_result(push, 0, "")], branch=self.branch(*self.UNITS))
        self.replay([stage(stage="landed", ref="origin/main", sha=self.sh("rev-parse", "HEAD")), bash_result(A_ANCHOR, 0, "ok"), bash_result(B_ANCHOR, 0, "ok")],
                    branch=self.branch(*self.UNITS))

    def step(self, **params) -> dict:
        """The tool's answer to one `anchorloop_stage` call."""
        return self.replay([stage(**params)], branch=self.branch(*self.UNITS))["results"][0]

    def lines(self) -> list[str]:
        return text_of(self.replay([stage(stage="read")], branch=self.branch(*self.UNITS))["results"][0]).splitlines()

    def unit_line(self, label: str) -> str:
        return next(line for line in self.lines() if line.startswith(label))


class TestTickALoopLevelItem(LoopObserveCase):
    def test_both_units_report_the_item_missing_until_it_is_ticked(self):
        self.start()
        self.assertIn(MISSING, self.unit_line("MP-1001"))
        self.assertIn(MISSING, self.unit_line("MP-1002"))

    def test_a_checkpoint_without_task_ticks_the_loops_item_in_a_book_of_two_units(self):
        self.start()
        answer = self.step(stage="verify", note="pipeline success, merged", checkpoint=1)
        self.assertNotIn("error", answer, answer)
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))

    def test_a_checkpoint_with_task_ticks_the_inherited_item_for_that_unit_only(self):
        self.start()
        answer = self.step(stage="verify", note="pipeline success", checkpoint=1, task=1)
        self.assertNotIn("error", answer, answer)
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertIn(MISSING, self.unit_line("MP-1002"))

    def test_a_number_the_loop_does_not_list_is_refused_naming_both_places(self):
        self.start()
        answer = self.step(stage="verify", note="x", checkpoint=2, task=1)
        self.assertIn("error", answer)
        self.assertIn("unit", answer["error"])
        self.assertIn("loop", answer["error"])


class TestTickWhenTheUnitListsItsOwn(LoopObserveCase):
    UNITS = (ONE_OWN, TWO)

    def test_the_loops_number_with_task_is_refused_and_the_error_names_both_places(self):
        self.start()
        self.assertNotIn("error", self.step(stage="verify", note="export loads", checkpoint=1, task=1))
        answer = self.step(stage="verify", note="x", checkpoint=2, task=1)
        self.assertIn("error", answer)
        self.assertIn("this unit", answer["error"])
        self.assertIn("loop", answer["error"])

    def test_a_loop_level_tick_does_not_hide_a_units_own_missing_observation(self):
        self.start()
        self.assertNotIn("error", self.step(stage="verify", note="pipeline success", checkpoint=1))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))
        self.assertIn(f"{MISSING} 1/1: {OWN}", self.unit_line("MP-1001"))


class TestDropALoopLevelItem(LoopObserveCase):
    def test_skip_with_phase_observe_and_a_checkpoint_drops_the_item_for_every_unit(self):
        self.start()
        answer = self.step(stage="skip", phase="observe", checkpoint=1, reason="MR !2 merged elsewhere, pipeline not ours to watch")
        self.assertNotIn("error", answer, answer)
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))

    def test_a_drop_needs_a_checkpoint_and_a_reason(self):
        self.start()
        self.assertIn("checkpoint", self.step(stage="skip", phase="observe", reason="done elsewhere")["error"])
        self.assertIn("reason", self.step(stage="skip", phase="observe", checkpoint=1)["error"])
        self.assertIn("error", self.step(stage="skip", phase="observe", checkpoint=3, reason="r"))
        self.assertIn(MISSING, self.unit_line("MP-1001"))

    def test_an_empty_observe_list_on_kind_is_refused_and_points_to_skip(self):
        self.start()
        answer = self.step(stage="kind", observe=[], reason="the item is done")
        self.assertIn("error", answer)
        self.assertIn("skip", answer["error"])
        self.assertIn(MISSING, self.unit_line("MP-1001"))

    def test_an_empty_observe_list_on_a_loop_with_no_items_is_accepted(self):
        self.shared_repo()
        self.replay(self.creates(*self.UNITS), branch=self.branch(*self.UNITS))
        self.assertNotIn("error", self.step(stage="kind", observe=[], reason="nothing listed"))



FIRST_ONLY = {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "kind": "inline", "observe": [OBSERVE]}}


class FirstTodoCase(LoopObserveCase):
    """The loop's list comes from the first todo's metadata (no `kind observe`); both units have landed and passed their anchors."""

    def start(self) -> None:  # type: ignore[override]
        self.shared_repo()
        self.replay(self.creates(*self.UNITS), branch=self.branch(*self.UNITS))
        self.land("fix")
        self.replay([stage(stage="landed", ref="origin/main", sha=self.sh("rev-parse", "HEAD")), bash_result(A_ANCHOR, 0, "ok"), bash_result(B_ANCHOR, 0, "ok")], branch=self.branch(*self.UNITS))

    def land(self, name: str) -> None:
        (self.cwd / "app.py").write_text(f"print({name!r})\n")
        push = f"git commit -qam '{name}' && git push -q origin main"
        self.replay([tool_call("write", "app.py"), edit("app.py"), bash_call(push), run("git", "commit", "-qam", name), run("git", "push", "-q", "origin", "main"), bash_result(push, 0, "")], branch=self.branch(*self.UNITS))

    def land_again(self) -> None:
        """A second landing, then both anchors run again."""
        self.land(f"fix {len(self.book()[1])}")
        self.replay([bash_result(A_ANCHOR, 0, "ok"), bash_result(B_ANCHOR, 0, "ok")], branch=self.branch(*self.UNITS))


def first_with(items: list) -> dict:
    return {**FIRST_ONLY, "metadata": {**FIRST_ONLY["metadata"], "observe": items}}


class TestTheFirstTodosListIsTheLoopsWhateverItsText(FirstTodoCase):
    """The first todo's list is stored for the loop and read for the unit: whatever its text, they are one list."""

    def check(self, items: list, kept: int = 1) -> None:
        self.UNITS = (first_with(items), TWO)
        self.start()
        self.assertIn(MISSING, self.unit_line("MP-1001"))
        for number in range(1, kept + 1):
            self.assertNotIn("error", self.step(stage="verify", note="seen", checkpoint=number))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))

    def test_a_trailing_space(self):
        self.check([OBSERVE + " "])

    def test_a_text_over_200_characters(self):
        self.check(["x" * 250])

    def test_an_item_that_is_not_a_string(self):
        self.check([5, OBSERVE])

    def test_more_than_ten_items(self):
        self.check([f"item {n}" for n in range(11)], kept=10)


class TestAUnitIsLinkedToTheLoopsListByItsTodoNotByEqualText(FirstTodoCase):
    OWN_TEXT = "pipeline green"
    UNITS = (
        {"subject": "MP-1001 export", "status": "in_progress", "metadata": {"anchor": A_ANCHOR, "kind": "inline", "observe": [OWN_TEXT]}},
        {"subject": "MP-1002 view", "status": "in_progress", "metadata": {"anchor": B_ANCHOR, "kind": "inline", "observe": [OWN_TEXT]}},
    )

    def test_a_tick_of_no_task_closes_the_first_todos_unit_only(self):
        self.start()
        self.assertNotIn("error", self.step(stage="verify", note="MR 1 pipeline green", checkpoint=1))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertIn(f"{MISSING} 1/1: {self.OWN_TEXT}", self.unit_line("MP-1002"))

    def test_a_drop_of_no_task_reaches_the_first_todos_unit_only(self):
        self.start()
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, reason="not ours"))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertIn(MISSING, self.unit_line("MP-1002"))


class TestTheFirstTodoListsItsOwnItemAndAnotherUnitListsNone(FirstTodoCase):
    UNITS = (first_with([OWN]), TWO)

    def test_a_tick_of_no_task_closes_the_unit_that_wrote_the_list_and_the_one_that_inherits_it(self):
        self.start()
        self.assertIn(f"{MISSING} 1/1: {OWN}", self.unit_line("MP-1001"))
        self.assertIn(f"{MISSING} 1/1: {OWN}", self.unit_line("MP-1002"))
        self.assertNotIn("error", self.step(stage="verify", note="loads", checkpoint=1))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))


class TestALandingAfterATick(FirstTodoCase):
    UNITS = (FIRST_ONLY, TWO)

    def test_a_tick_holds_until_the_next_landing_and_a_drop_does_not_end_with_it(self):
        self.start()
        self.assertNotIn("error", self.step(stage="verify", note="seen", checkpoint=1))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.land_again()
        self.assertIn(MISSING, self.unit_line("MP-1001"))
        self.assertIn(MISSING, self.unit_line("MP-1002"))
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, reason="not ours to watch"))
        self.land_again()
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))


class TestAnEmptyObserveListWhileAUnitListsItems(LoopObserveCase):
    """No loop-level items; todo 2 lists its own: `kind observe: []` would drop nothing, so it is refused and points to the drop."""

    UNITS = (ONE, {**TWO, "metadata": {**TWO["metadata"], "observe": ["prod health 200"]}})

    def start(self) -> None:  # type: ignore[override]
        self.shared_repo()
        self.replay(self.creates(*self.UNITS), branch=self.branch(*self.UNITS))

    def test_it_is_refused_naming_skip_and_the_task(self):
        self.start()
        answer = self.step(stage="kind", observe=[], reason="the item is done")
        self.assertIn("skip", answer["error"])
        self.assertIn("task: 2", answer["error"])

    def test_the_drop_it_points_to_closes_the_item(self):
        self.start()
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, task=2, reason="done elsewhere"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))


PLAIN = {"subject": "ship it", "status": "in_progress", "metadata": {"anchor": A_ANCHOR}}
WATCH = {"subject": "MP-1002 watch", "status": "in_progress", "metadata": {"observe": ["prod health 200"]}}


class TestOneUnitReadsTheLoopsList(LoopObserveCase):
    """One unit (todo 2 lists its own item) and a loop item from `kind observe`: the phases read the loop's list, so a number with `task` means the loop's item."""

    UNITS = (PLAIN, WATCH)

    def test_a_tick_with_task_ticks_what_the_phases_read(self):
        self.start()
        self.assertIn(MISSING, self.lines()[0])
        self.assertNotIn("error", self.step(stage="verify", note="pipeline green", checkpoint=1, task=2))
        self.assertNotIn(MISSING, self.lines()[0])

    def test_a_drop_with_task_drops_what_the_phases_read(self):
        self.start()
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, task=2, reason="done"))
        first = self.lines()[0]
        self.assertNotIn(MISSING, first)
        self.assertIn("skipped: observe 1 (done)", first)

    def test_a_number_only_the_unit_lists_is_refused_instead_of_recorded_for_nothing(self):
        self.start()
        self.assertIn("error", self.step(stage="verify", note="x", checkpoint=2, task=2))
        self.assertIn(MISSING, self.lines()[0])


class TestADropOutlivesTheLoop(LoopObserveCase):
    def test_read_and_the_close_summary_carry_the_item_and_its_reason(self):
        self.start()
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, reason="DROPREASON"))
        self.assertIn("skipped: observe 1 (DROPREASON)", self.lines()[0])
        closed = [{**task, "status": "completed"} for task in self.UNITS]
        out = self.replay([stage(stage="close", verdict="landed")], branch=[todo_state(*closed)])
        self.assertIn("observe 1 (DROPREASON)", str(out["appended"]))

    def test_a_unit_s_own_drop_is_named_with_the_unit(self):
        self.shared_repo()
        units = (ONE_OWN, TWO)
        self.replay(self.creates(*units), branch=self.branch(*units))
        answer = self.replay([stage(stage="skip", phase="observe", checkpoint=1, task=1, reason="OWNREASON")], branch=self.branch(*units))["results"][0]
        self.assertNotIn("error", answer)
        closed = [{**task, "status": "completed"} for task in units]
        out = self.replay([stage(stage="close", verdict="abandoned")], branch=[todo_state(*closed)])
        self.assertIn("MP-1001 observe 1 (OWNREASON)", str(out["appended"]))


class TestEveryUnitListsItsOwnAndTheLoopListsOne(LoopObserveCase):
    """`kind observe` gave a loop item that no unit reads: the loop is not complete until it is ticked or dropped."""

    UNITS = (ONE_OWN, {**TWO, "metadata": {**TWO["metadata"], "observe": ["view loads"]}})

    def done_units(self) -> None:
        self.assertNotIn("error", self.step(stage="verify", note="ok", checkpoint=1, task=1))
        self.assertNotIn("error", self.step(stage="verify", note="ok", checkpoint=1, task=2))
        self.assertNotIn(MISSING, self.unit_line("MP-1001"))
        self.assertNotIn(MISSING, self.unit_line("MP-1002"))

    def test_the_loop_line_names_the_item_after_every_unit_is_done(self):
        self.start()
        self.done_units()
        first = self.lines()[0]
        self.assertIn(f"{MISSING} 1/1: {OBSERVE}", first)
        self.assertIn("→ verify", first)

    def test_a_tick_of_no_task_closes_it(self):
        self.start()
        self.done_units()
        self.assertNotIn("error", self.step(stage="verify", note="pipeline green", checkpoint=1))
        first = self.lines()[0]
        self.assertNotIn(MISSING, first)
        self.assertIn("→ close", first)

    def test_a_drop_closes_it_and_the_loop_line_carries_it(self):
        self.start()
        self.done_units()
        self.assertNotIn("error", self.step(stage="skip", phase="observe", checkpoint=1, reason="LOOPDROP"))
        first = self.lines()[0]
        self.assertIn("skipped: observe 1 (LOOPDROP)", first)
        self.assertNotIn(MISSING, first)

    def test_close_names_it_as_not_complete(self):
        self.start()
        self.done_units()
        closed = [{**task, "status": "completed"} for task in self.UNITS]
        out = self.replay([stage(stage="close", verdict="landed")], branch=[todo_state(*closed)])
        self.assertIn(OBSERVE, text_of(out["results"][0]))
