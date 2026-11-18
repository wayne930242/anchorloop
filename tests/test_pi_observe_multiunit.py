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

