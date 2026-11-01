"""Anchor reruns record their own one-line friction, already reflected as resolved, and the widget below the editor shows the loop's kind and phase."""

from tests.pi_harness import assistant, bash_result, stage, todo_create, todo_update, tool_result
from tests.test_pi_book import BookCase, edit, text_of

PYTEST_FAIL = "\n".join([
    "============================= test session starts ==============================",
    "tests/test_x.py F",
    "    def test_x():",
    ">       assert add(1, 2) == 4",
    "E       assert 3 == 4",
    "Traceback (most recent call last):",
    '  File "x.py", line 3, in <module>',
    "FAILED tests/test_x.py::test_x - assert 3 == 4",
    "========================= 1 failed, 4 passed in 0.12s ==========================",
])


class TestAutoFriction(BookCase):
    def rerun(self, failing_output: str = PYTEST_FAIL, between: list | None = None) -> dict:
        return self.replay([
            *self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "5 passed"),
            edit(), bash_result("pytest -q", 1, failing_output), *(between or []),
            edit(), bash_result("pytest -q", 0, "5 passed"),
        ])

    def test_a_rerun_that_passes_again_records_one_short_friction_line(self):
        out = self.rerun()
        [friction] = self.entries("friction")
        self.assertTrue(friction["auto"])
        self.assertIn("pytest -q", friction["tried"])
        self.assertIn("FAILED tests/test_x.py::test_x - assert 3 == 4", friction["found"])
        self.assertLessEqual(len(friction["found"]), 120)
        self.assertNotIn("Traceback", friction["found"])
        self.assertIsNone(out["results"][-1])
        self.assertEqual(self.entries("friction"), [friction])

    def test_the_key_line_is_cut_to_120_characters(self):
        self.rerun("error: " + "x" * 400)
        [friction] = self.entries("friction")
        self.assertLessEqual(len(friction["found"]), 120)
        self.assertLessEqual(max(len(entry.get("key", "")) for entry in self.entries("verify")), 120)
        self.assertTrue(friction["found"].endswith("…"))

    def test_stack_frames_never_stand_in_for_the_key_line(self):
        self.rerun('boom happened\n  File "lib/error_utils.py", line 3, in run\n    at handleError (lib/x.js:1:1)')
        self.assertEqual(self.entries("friction")[0]["found"], "boom happened")

    def test_a_python_exception_line_beats_the_code_inside_its_traceback(self):
        self.rerun('Traceback (most recent call last):\n  File "x.py", line 3, in <module>\n    log.error("bad")\nValueError: boom')
        self.assertEqual(self.entries("friction")[0]["found"], "ValueError: boom")

    def test_an_exception_name_is_a_key_line(self):
        self.rerun("ValueError: boom\nexit status 1")
        self.assertEqual(self.entries("friction")[0]["found"], "ValueError: boom")

    def test_the_source_a_python_frame_quotes_is_not_a_key_line(self):
        self.rerun('  File "x.py", line 3, in run\n    log.error("bad")\nboom')
        self.assertEqual(self.entries("friction")[0]["found"], "boom")

    def test_each_anchor_regression_gets_its_own_entry(self):
        task = {"id": 1, "subject": "write the fix", "status": "in_progress", "metadata": {"anchor": "npm test"}}
        update = tool_result("todo", {"action": "update", "id": 1, "status": "in_progress"}, "updated", details={"tasks": [task], "nextId": 2})
        self.replay([*self.open_loop(anchor="pytest -q"), update, edit(), bash_result("pytest -q", 0, "ok"), bash_result("npm test", 0, "ok"),
                     bash_result("npm test", 1, "Error: npm broke"), bash_result("pytest -q", 1, "E   assert 1 == 2"), bash_result("pytest -q", 0, "ok"),
                     bash_result("npm test", 0, "ok")])
        self.assertEqual(sorted(entry["found"] for entry in self.entries("friction")), ["E   assert 1 == 2", "Error: npm broke"])

    def test_one_run_of_an_anchor_shared_by_loop_and_task_is_one_entry(self):
        task = {"id": 1, "subject": "write the fix", "status": "in_progress", "metadata": {"anchor": "pytest -q"}}
        update = tool_result("todo", {"action": "update", "id": 1, "status": "in_progress"}, "updated", details={"tasks": [task], "nextId": 2})
        self.replay([*self.open_loop(anchor="pytest -q"), update, edit(), bash_result("pytest -q", 0, "ok"), bash_result("pytest -q", 1, "E   x"),
                     bash_result("pytest -q", 0, "ok")])
        self.assertEqual(len(self.entries("friction")), 1)

    def test_a_failure_recorded_before_the_key_line_existed_still_gives_a_key_line(self):
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok")])
        book = self.book_files()[0]
        old = {"stage": "verify", "command": "pytest -q", "exit": 1, "last": '  File "x.py", line 3, in run'}
        text = book.read_text()
        book.write_text(text + ("  - " if "\n  - " in text else "- ") + __import__("json").dumps(old) + "\n")
        self.replay([bash_result("pytest -q", 0, "ok")])
        self.assertEqual([entry["found"] for entry in self.entries("friction")], ["failed with no output"])

    def test_a_backfilled_older_pair_does_not_speak_for_the_newer_failure(self):
        import json
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok")])
        book = self.book_files()[0]
        text = book.read_text()
        lead = "  - " if "\n  - " in text else "- "
        # Both pairs stay open only when entries land without a bash call between them, as a book written elsewhere can.
        for entry in ({"stage": "verify", "command": "pytest -q", "exit": 1, "last": "old failure"}, {"stage": "verify", "command": "pytest -q", "exit": 0, "last": "ok"},
                      {"stage": "verify", "command": "pytest -q", "exit": 1, "key": "E   new failure", "last": "1 failed"}):
            text += lead + json.dumps(entry) + "\n"
        book.write_text(text)
        self.replay([bash_result("pytest -q", 0, "ok")])
        self.assertEqual([entry["found"] for entry in self.entries("friction")], ["E   new failure"])

    def test_without_an_error_line_the_last_line_is_kept(self):
        self.rerun("compiling\n3 checks did not pass")
        self.assertIn("3 checks did not pass", self.entries("friction")[0]["found"])

    def test_red_first_work_records_nothing(self):
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 1, PYTEST_FAIL), edit(), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.entries("friction"), [])

    def test_a_friction_the_agent_recorded_after_the_failure_is_not_doubled(self):
        self.rerun(between=[stage(stage="friction", tried="pytest -q after the rename", found="import path changed")])
        self.assertEqual([entry.get("auto", False) for entry in self.entries("friction")], [False])

    def test_a_task_anchor_rerun_records_friction_too(self):
        task = {"id": 1, "subject": "write the fix", "status": "in_progress", "metadata": {"anchor": "npm test"}}
        update = tool_result("todo", {"action": "update", "id": 1, "status": "in_progress"}, "updated", details={"tasks": [task], "nextId": 2})
        self.replay([*self.open_loop(anchor="pytest -q"), update, edit(), bash_result("npm test", 0, "ok"), edit(),
                     bash_result("npm test", 1, "Error: expected 2 got 3\n    at foo (a.js:1:1)"), edit(), bash_result("npm test", 0, "ok")])
        [friction] = self.entries("friction")
        self.assertIn("npm test", friction["tried"])
        self.assertIn("Error: expected 2 got 3", friction["found"])

    def test_the_auto_friction_is_reflected_as_resolved_at_once(self):
        self.rerun()
        [reflect] = self.entries("reflect")
        self.assertEqual((reflect["friction"], reflect["class"]), (["1"], "resolved"))
        out = self.replay([stage(stage="read")])
        self.assertIn("friction: 1 (0 unreflected)", text_of(out["results"][-1]))
        self.assertNotIn("without a reflect", text_of(out["results"][-1]))

    def test_a_friction_the_agent_records_still_waits_for_a_reflect(self):
        self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="friction", tried="a", found="b", led_by="the playbook")])
        out = self.replay([stage(stage="read")])
        self.assertIn("friction: 1 (1 unreflected)", text_of(out["results"][-1]))


class TestLoopWidget(BookCase):
    def last_widget(self, out: dict):
        mine = [widget for widget in out["widgets"] if widget["key"] == "anchorloop"]
        return mine[-1] if mine else "never set"

    def last_line(self, out: dict) -> str | None:
        widget = self.last_widget(out)
        return widget["lines"][0] if widget["lines"] else None

    def test_the_widget_sits_below_the_editor_and_names_the_kind_and_the_phase(self):
        out = self.replay([*self.open_loop(kind="reviewed", anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok")])
        widget = self.last_widget(out)
        self.assertEqual((widget["lines"], widget["placement"]), (["⚓ reviewed · verify ✓ → review"], "belowEditor"))
        self.assertEqual(out["statuses"], [])

    def test_a_failed_check_shows_fix_next(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 1, "1 failed")])
        self.assertEqual(self.last_line(out), "⚓ inline · act ✓ → fix")

    def test_unreflected_friction_is_counted(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="friction", tried="a", found="b")])
        self.assertTrue(self.last_line(out).endswith(" · 1 friction"))

    def test_a_reflected_friction_is_not_counted(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="friction", tried="a", found="b"), stage(stage="reflect", friction=[1], **{"class": "resolved"})])
        self.assertNotIn("friction", self.last_line(out))

    def test_the_first_todo_create_shows_an_inline_loop(self):
        out = self.replay([todo_create()])
        self.assertEqual(self.last_line(out), "⚓ inline · start → anchor")

    def test_closing_the_loop_clears_the_widget(self):
        out = self.replay([*self.open_loop(kind="quick"), stage(stage="skip", phase="act", reason="nothing"), todo_update(1, "write the fix", "completed"),
                           stage(stage="close", verdict="abandoned")])
        self.assertIsNone(self.last_widget(out)["lines"])

    def test_session_start_shows_an_open_loop_again(self):
        self.replay([*self.open_loop(anchor="pytest -q")])
        out = self.replay([{"event": "session_start", "payload": {}}])
        self.assertEqual(self.last_line(out), "⚓ inline · anchor ✓ → act")

    def test_a_reality_anchor_line_updates_the_widget_without_a_tool_call(self):
        out = self.replay([todo_create(), assistant("Reality anchor: pytest -q")])
        widgets = [widget for widget in out["widgets"] if widget["key"] == "anchorloop"]
        self.assertEqual(widgets[0]["lines"], ["⚓ inline · start → anchor"])
        self.assertEqual(widgets[-1]["lines"], ["⚓ inline · anchor ✓ → act"])
