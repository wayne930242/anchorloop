"""The anchor gate, the decision trail tool, and the Jev second thought, replayed against stub pi events."""

import tempfile
import unittest
from pathlib import Path

from tests.pi_harness import (
    SETTLE,
    SETTLED,
    ExtensionCase,
    assistant,
    bash_result,
    stage,
    todo_create,
    todo_state,
    todo_update,
    tool_call,
    tool_result,
    user_start,
    write_file,
)


DIR = "docs/specs/2026-10-29-x"
ROWS = "| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which db? | pg | req | grounded |\n| Cache? | yes | user | confirmed |\n"
DESIGN = "## Approach\n\nUse the existing table.\n"


def touch(tool: str, path: str = "src/app.py", call_id: str = "c1") -> list[dict]:
    """An edit as pi runs it: the tool call, then its result."""
    return [tool_call(tool, path, call_id), tool_result(tool, {"path": path}, call_id=call_id)]


class TestAnchorGate(ExtensionCase):
    extensions = ("book.ts", "anchor-gate.ts")

    def lines(self, out: dict) -> list[tuple[int, str]]:
        """The (step of the call, warning line) of each edit result that carries the gate's line; the warning reaches the agent in the tool result."""
        found = []
        for step, result in enumerate(out["results"]):
            for block in (result or {}).get("content", []):
                if block["text"].startswith("anchorloop: before"):
                    self.assertNotIn("\n", block["text"])
                    found.append((step - 1, block["text"]))
        return found

    def warned_steps(self, out: dict) -> list[int]:
        self.assertEqual(out["notices"], [])
        return [step for step, _ in self.lines(out)]

    def loop(self, kind: str | None = "inline", **extra) -> list[dict]:
        steps = [{"event": "session_start"}, user_start(), todo_create()]
        return steps + ([stage(stage="kind", kind=kind, intent="x", **extra)] if kind else [])

    def test_without_an_open_loop_nothing_is_gated(self):
        out = self.replay([{"event": "session_start"}, user_start(), *touch("edit"), *touch("write")])
        self.assertEqual(out["notices"], [])

    def test_an_edit_without_an_anchor_warns_once_in_one_line_in_the_edit_result_and_never_blocks(self):
        out = self.replay([*self.loop(), *touch("edit"), *touch("write"), user_start("now the import"), *touch("edit")])
        self.assertEqual(self.warned_steps(out), [4])
        [(_, message)] = self.lines(out)
        self.assertEqual(message, "anchorloop: before act, still missing: anchor (a `Reality anchor:` line, `metadata.anchor` on the first todo, or `anchor` on the kind call).")
        # The warning is the only addition to the edit's own result; later edits are untouched.
        self.assertEqual([block["text"] for block in out["results"][5]["content"]], ["ok", message])
        self.assertTrue(all(result is None for result in out["results"][6:]))

    def test_the_warning_is_not_a_notification_to_the_user(self):
        self.assertEqual(self.replay([*self.loop(), *touch("edit")])["notices"], [])

    def test_an_edit_in_a_loop_a_todo_create_opened_is_gated_like_inline(self):
        self.assertEqual(self.warned_steps(self.replay([*self.loop(None), *touch("edit")])), [3])

    def test_a_quick_loop_has_no_phase_warnings(self):
        self.assertEqual(self.replay([*self.loop("quick"), *touch("edit")])["notices"], [])

    def test_the_reality_anchor_line_silences_the_warning(self):
        out = self.replay([*self.loop(), assistant("Alignment: fix it.\nReality anchor: pytest tests/test_export.py"), *touch("write"), user_start("now the import"), *touch("write")])
        self.assertEqual(out["notices"], [])

    def test_a_reality_anchor_line_stated_before_the_loop_opened_counts(self):
        branch = [{"type": "message", "message": {"role": "user", "content": "fix it"}},
                  {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest"}]}}]
        self.assertEqual(self.replay([{"event": "session_start"}, todo_create(), stage(stage="kind", kind="inline", intent="x"), *touch("edit")], branch=branch)["notices"], [])

    def test_a_reality_anchor_line_stated_before_the_last_user_message_does_not_count(self):
        branch = [{"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest"}]}},
                  {"type": "message", "message": {"role": "user", "content": "now the import"}}]
        out = self.replay([{"event": "session_start"}, todo_create(), *touch("edit")], branch=branch)
        self.assertEqual(self.warned_steps(out), [2])

    def test_the_anchor_on_the_kind_call_and_a_skipped_anchor_both_count(self):
        self.assertEqual(self.replay([*self.loop(anchor="pytest"), *touch("edit")])["notices"], [])
        self.assertEqual(self.replay([stage(stage="skip", phase="anchor", reason="no check exists"), *touch("edit")], session="s2")["notices"], [])

    def test_text_and_html_files_scratch_specs_temp_paths_and_other_tools_pass(self):
        out = self.replay([
            *self.loop(),
            *touch("write", "README.md"),
            *touch("edit", "notes/todo.TXT"),
            *touch("write", "report/index.html"),
            *touch("edit", "legacy/page.HTM"),
            *touch("write", "scratch/friction.json"),
            *touch("edit", "docs/specs/2026-10-21-x/design.html"),
            *touch("write", str(Path(tempfile.gettempdir()) / "anchorloop-gate-outside" / "page.html")),
            tool_call("bash"),
        ])
        self.assertEqual(out["notices"], [])

    def test_the_warning_comes_again_only_when_a_jump_adds_a_phase_that_was_not_warned_about(self):
        steps = [*self.loop(), *touch("edit"), *touch("edit"), stage(stage="kind", anchor="pytest"), *touch("edit"),
                 stage(stage="back", phase="anchor", reason="the anchor was wrong"), *touch("edit")]
        self.assertEqual(self.warned_steps(self.replay(steps)), [4, 12])

    def test_a_durable_loop_names_every_missing_phase_in_one_warning(self):
        out = self.replay([*self.loop("durable"), *touch("edit"), *touch("edit", "src/b.py")])
        self.assertEqual(self.warned_steps(out), [4])
        message = self.lines(out)[0][1]
        for phase in ("decide", "grill", "spec", "read", "approve", "design", "anchor"):
            self.assertIn(f"{phase} (", message)

    def artifact(self, name: str, text: str) -> dict:
        path = self.cwd / DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return tool_result("write", {"path": f"{DIR}/{name}"})

    def ready(self, status: str = "approved") -> list[dict]:
        spec = f"Status: {status}\nApproved from: user\n\n# Spec\n"
        return [*self.loop("durable", anchor="pytest"), self.artifact("decision.md", ROWS), self.artifact("spec.md", spec), stage(stage="fresh-read"), self.artifact("design.md", DESIGN)]

    def test_a_durable_production_edit_with_every_earlier_phase_complete_is_silent(self):
        self.assertEqual(self.replay([*self.ready(), *touch("edit")])["notices"], [])

    def test_a_durable_production_edit_warns_while_the_spec_is_not_approved(self):
        out = self.replay([*self.ready("proposed"), *touch("edit"), *touch("edit", "src/b.py")])
        self.assertEqual(self.warned_steps(out), [8])
        self.assertIn("approve (spec.md Status: approved with Approved from (now proposed))", self.lines(out)[0][1])

    def test_a_spec_edited_back_to_proposed_makes_the_next_edit_warn_again(self):
        spec = f"{DIR}/spec.md"
        out = self.replay([*self.ready(), *touch("edit"), write_file(spec, "Status: proposed\n"), tool_result("write", {"path": spec}), *touch("edit"), *touch("edit")])
        self.assertEqual(self.warned_steps(out), [12])
        self.assertIn("approve (", self.lines(out)[0][1])

    def test_spec_and_doc_edits_in_a_durable_loop_are_not_production_edits(self):
        out = self.replay([*self.loop("durable"), *touch("edit", f"{DIR}/design.md"), *touch("write", "notes.md")])
        self.assertEqual(out["notices"], [])

    def test_a_pickup_loop_that_names_the_spec_in_its_intent_reads_the_phases_from_disk(self):
        for name, text in (("decision.md", ROWS), ("spec.md", "Status: approved\nApproved from: user\n"), ("design.md", DESIGN)):
            self.artifact(name, text)
        steps = [{"event": "session_start"}, user_start(), todo_create(), stage(stage="kind", kind="durable", intent=f"implement {DIR}", anchor="pytest"), *touch("edit")]
        self.assertEqual(self.replay(steps)["notices"], [])

    def test_an_inline_loop_ignores_the_artifact_phases(self):
        self.assertEqual(self.replay([*self.loop(anchor="x"), *touch("edit")])["notices"], [])

    def test_a_book_that_cannot_be_written_never_blocks_a_tool(self):
        # RV-F011: the books path is a file, so every book read or write fails.
        blocker = self.cwd.parent / "not-a-dir"
        blocker.write_text("x")
        steps = [{"event": "session_start"}, todo_create(), *touch("edit"), tool_result("write", {"path": "src/a.py"}), bash_result("pytest", 0, "ok"), assistant("Reality anchor: x")]
        out = self.replay(steps, env={"ANCHORLOOP_BOOKS_DIR": str(blocker)})
        self.assertTrue(all(result is None for result in out["results"]), out["results"])


class TestDecisionTool(ExtensionCase):
    extension = "decision-tool.ts"

    def rows(self) -> list[list[str]]:
        return [line.split("\t") for line in (self.cwd / "scratch/decisions-t.tsv").read_text().splitlines()]

    def test_first_row_writes_the_header_and_cells_stay_single_line_and_formula_safe(self):
        self.replay([
            {"tool": "anchorloop_decision", "params": {"log": "scratch/decisions-t.tsv", "decision": "a\tb\nc",
                                                  "why": "=HYPERLINK(1)", "evidence": "-rf", "result": "@x"}},
        ])
        rows = self.rows()
        self.assertEqual(rows[0], ["ts", "decision", "why", "evidence", "result"])
        self.assertEqual(rows[1][1:], ["a b c", "'=HYPERLINK(1)", "'-rf", "'@x"])

    def test_start_row_names_the_run_and_the_rows_before_it(self):
        self.replay([
            {"tool": "anchorloop_decision", "params": {"log": "scratch/decisions-t.tsv", "decision": "first", "why": "w",
                                                  "evidence": "abc123", "result": "open"}},
            {"tool": "anchorloop_decision", "params": {"log": "scratch/decisions-t.tsv", "start": "worker-2"}},
        ])
        last = self.rows()[-1]
        self.assertEqual(last[1], "start")
        self.assertIn("1 earlier rows", last[2])
        self.assertEqual(last[3:], ["worker-2", "open"])

    def test_a_log_outside_the_scratch_trail_is_refused(self):
        out = self.replay([{"tool": "anchorloop_decision", "params": {"log": "src/app.py", "decision": "d", "why": "w",
                                                                   "evidence": "e", "result": "r"}}])
        self.assertIn("scratch/decisions-", out["results"][0]["error"])
        self.assertFalse((self.cwd / "src/app.py").exists())

    def test_missing_cells_fail_without_writing(self):
        out = self.replay([{"tool": "anchorloop_decision", "params": {"log": "scratch/decisions-t.tsv", "decision": "only"}}])
        self.assertIn("all required", out["results"][0]["error"])
        self.assertFalse((self.cwd / "scratch/decisions-t.tsv").exists())


class TestSecondThought(ExtensionCase):
    extensions = ("book.ts", "second-thought.ts")

    def loop(self, kind: str = "inline", *more: dict) -> list[dict]:
        return [user_start(), todo_create(), stage(stage="kind", kind=kind, intent="fix the export", anchor="pytest -q"), *more]

    def settle_after(self, classify: object, *more: dict, kind: str = "inline", extra: list[dict] | None = None) -> dict:
        return self.replay([*self.loop(kind, *more), SETTLE, *(extra or [])], classify=classify)

    def content(self, out: dict) -> str:
        return self.advice(out["results"][-1]) or self.fail(f"no advisory in {out['results'][-1]}")

    def advice(self, result: dict | None) -> str | None:
        """The advisory text a settle result carries, or None when the result says nothing."""
        messages = [entry for entry in (result or {}).get("entries", []) if entry["type"] == "custom_message"]
        return messages[-1]["content"] if messages else None

    def test_without_a_loop_nothing_is_asked_or_recorded(self):
        out = self.replay([user_start(), tool_call("bash"), assistant("Done."), SETTLE], classify=answers("advance"))
        self.assertIsNone(out["results"][3])
        self.assertEqual(out["classifyCalls"], [])

    def test_jev_sees_only_the_book_state_with_the_phase_and_judges_the_move_and_completion(self):
        self.git_repo()
        (self.cwd / "app.py").write_text("print(1)\nprint(2)\n")
        todos = todo_state({"subject": "build it", "status": "in_progress", "metadata": {"anchor": "pytest -q", "ref": "docs/x.md#Gone"}},
                           {"subject": "done", "status": "completed"})
        out = self.replay([
            user_start(), todo_create("build it", anchor="pytest -q", ref="docs/x.md#Gone"), todo_create("done", task_id=2, status="completed"),
            stage(stage="kind", kind="reviewed", intent="fix the export", anchor="pytest -q"),
            {"event": "tool_call", "payload": {"toolName": "edit", "toolCallId": "e", "input": {"path": "app.py"}}},
            edit_result("app.py"), {"branchAdd": [todos]}, bash_result("pytest -q", 0, "3 passed"),
            stage(stage="friction", tried="a", found="b"), SETTLE,
        ], classify=answers())
        (state,) = out["classifyCalls"]
        self.assertEqual(sorted(state), ["anchor", "diff", "friction", "intent", "kind", "phase", "tasks", "todos", "verify"])
        self.assertEqual((state["kind"], state["intent"], state["anchor"]), ("reviewed", "fix the export", "pytest -q"))
        self.assertIn("1 file changed", state["diff"])
        self.assertLessEqual(len(state["diff"]), 1200)
        self.assertEqual(state["phase"], "current: verify; next: review; missing: a review round after the last change with Blocking: P0=0 P1=0")
        self.assertIn("last check: exit 0 — 3 passed", state["verify"])
        self.assertEqual(state["todos"], "1 open of 2: #1 build it")
        self.assertEqual(state["friction"], "1 recorded, 0 reflected\n1: a → b [unreflected]")
        legend, task = state["tasks"].splitlines()[:2]
        self.assertEqual(legend, "legend: #id status subject — anchor (last exit) — ref → line range; missing = heading gone")
        self.assertEqual(task, "#1 in_progress build it — pytest -q (exit 0) — docs/x.md#Gone → missing")
        self.assertEqual(out["questionSets"], [["move", "done", "review", "quality"]])

    def test_a_childs_friction_shows_in_the_state_under_its_child_name(self):
        env = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "worker-1", "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay([todo_create(), stage(stage="kind", kind="inline", intent="child"), stage(stage="friction", tried="old cmd", found="renamed")], env=env)
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "worker-1", "agent": "worker", "status": "started"})
        out = self.replay([*self.loop(), link, SETTLE], classify=answers())
        self.assertIn("worker-1#1: old cmd → renamed [unreflected]", out["classifyCalls"][0]["friction"])

    def test_jev_agreeing_with_no_concerns_and_no_open_todos_says_nothing_but_the_verdict_is_recorded(self):
        out = self.settle_after(answers(), edit_result(), bash_result("pytest -q", 0, "3 passed"))
        result = out["results"][-1]
        self.assertIsNone(self.advice(result))
        self.assertEqual([entry["type"] for entry in result["entries"]], ["custom"])
        self.assertEqual(result["entries"][0]["data"]["move"], "advance")
        self.assertNotIn("continue", result)

    def test_the_advisory_is_the_next_phase_and_its_gap_without_scores(self):
        out = self.settle_after(answers(), edit_result())
        self.assertEqual(self.content(out), "next: verify (a passing run of `pytest -q` after the last change)")
        self.assertTrue(out["results"][-1]["continue"])

    def test_concerns_follow_the_next_line_and_no_score_or_prefix_is_shown(self):
        out = self.settle_after(answers("advance", done=0.05, quality=0.5), edit_result(), bash_result("pytest -q", 0, "ok"))
        self.assertEqual(self.content(out), "next: close\nconcerns: evidence not shown to cover the intent; result below the intent")
        self.assertNotIn("continue", out["results"][-1])
        self.assertNotIn("Jev", self.content(out))
        self.assertNotIn("0.", self.content(out))

    def test_a_verify_phase_continues_the_run_once_when_jev_agrees_to_advance(self):
        out = self.replay([*self.loop(), edit_result(), SETTLE, bash_result("pytest -q", 1, "bad"), SETTLED, edit_result(), SETTLE], classify=answers())
        first = out["results"][4]
        self.assertTrue(first["continue"])
        self.assertEqual(self.advice(first), "next: verify (a passing run of `pytest -q` after the last change)")
        # The same advice a second time is not repeated, though the verdict is recorded again.
        self.assertIsNone(self.advice(out["results"][8]))
        self.assertEqual(len(out["results"][8]["entries"]), 1)

    def open_todos(self, *tasks: dict) -> dict:
        return {"branchAdd": [todo_state(*tasks)]}

    def test_open_todos_are_listed_in_the_advisory_with_the_call_to_settle_each(self):
        out = self.settle_after(answers(), self.open_todos({"subject": "port the cache", "status": "pending"}, {"subject": "done", "status": "completed"}),
                                bash_result("pytest -q", 0, "ok"))
        self.assertEqual(self.content(out), "next: act (a change to the code)\nopen: #1 port the cache — continue each, complete it, or set metadata.followup (a ticket id, `memory`, or `drop — <reason>`)")
        self.assertEqual(out["classifyCalls"][0]["todos"], "1 open of 2: #1 port the cache")

    def test_the_todo_list_is_bounded(self):
        tasks = [{"subject": f"task {n} " + "x" * 200, "status": "pending"} for n in range(1, 9)]
        out = self.settle_after(answers(), self.open_todos(*tasks))
        text = self.content(out)
        self.assertIn("#3 task 3", text)
        self.assertNotIn("#4 task 4", text)
        self.assertIn("+5 more", text)
        self.assertNotIn("x" * 61, text)
        self.assertIn("…; #2", text)

    def test_open_todos_continue_the_run_even_when_the_next_phase_is_not_actionable(self):
        out = self.settle_after(answers(), self.open_todos({"subject": "port the cache", "status": "in_progress"}), edit_result(), bash_result("pytest -q", 0, "ok"))
        self.assertTrue(self.content(out).startswith("next: close\nopen: #1 port the cache"))
        self.assertTrue(out["results"][-1]["continue"])

    def test_open_todos_continue_the_run_once_per_run(self):
        todos = self.open_todos({"subject": "port the cache", "status": "pending"})
        out = self.replay([*self.loop(), todos, SETTLE, edit_result(), SETTLE], classify=answers())
        self.assertTrue(out["results"][4]["continue"])
        self.assertNotIn("continue", out["results"][6])

    def test_ask_user_with_open_todos_tells_the_agent_to_ask_and_does_not_continue(self):
        out = self.settle_after(answers("ask-user"), self.open_todos({"subject": "port the cache", "status": "pending"}))
        self.assertNotIn("continue", out["results"][-1])
        text = self.content(out)
        self.assertIn("open: #1 port the cache — ask the user about them with ask_user_question", text)
        self.assertIn("concerns: needs the user's decision", text)
        self.assertNotIn("continue each", text)

    def test_a_todo_with_a_valid_followup_is_no_longer_called_out(self):
        out = self.settle_after(answers(), self.open_todos({"subject": "later", "status": "pending", "metadata": {"followup": "MP-12"}}))
        self.assertIsNone(self.advice(out["results"][-1]))
        self.assertNotIn("continue", out["results"][-1])
        self.assertEqual(out["classifyCalls"][0]["todos"], "1 open of 1 (1 with a followup)")

    def test_without_open_todos_a_finished_loop_hears_nothing(self):
        out = self.settle_after(answers(), self.open_todos({"subject": "done", "status": "completed"}), edit_result(), bash_result("pytest -q", 0, "3 passed"))
        self.assertIsNone(self.advice(out["results"][-1]))
        self.assertNotIn("continue", out["results"][-1])

    def test_an_unchanged_advisory_is_not_repeated_when_todos_change_around_it_but_a_new_open_todo_speaks_again(self):
        first = self.open_todos({"subject": "port the cache", "status": "pending"})
        edited = self.open_todos({"subject": "port the cache NOW", "status": "pending"})
        more = self.open_todos({"subject": "port the cache", "status": "pending"}, {"subject": "second", "status": "pending"})
        out = self.replay([*self.loop(), first, SETTLE, SETTLED, edited, stage(stage="friction", tried="a", found="b"), SETTLE, SETTLED, more, stage(stage="friction", tried="c", found="d"), SETTLE],
                          classify=answers())
        spoken = [self.advice(result) for result in out["results"] if result and "entries" in result]
        # The reworded subject keeps the same ids, so only the first and the third settle speak.
        self.assertEqual([text is not None for text in spoken], [True, False, True])
        self.assertIn("#2 second", spoken[2])

    def test_open_todos_are_not_listed_in_the_close_advisory(self):
        steps = [*self.loop(), edit_result(), self.open_todos({"subject": "port the cache", "status": "pending"}),
                 {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}},
                 stage(stage="close", verdict="landed"),
                 tool_result("anchorloop_stage", {"stage": "close", "verdict": "landed"}, "Loop closed (landed)", call_id="c9")]
        result = self.replay(steps, classify=answers("advance", done=0.05))["results"][-1]
        self.assertEqual(result["content"][1]["text"], "\nJev: evidence not shown to cover the intent.")
        self.assertNotIn("port the cache", result["content"][1]["text"])

    def test_a_waiting_run_with_open_todos_is_not_judged(self):
        out = self.replay([*self.loop(), self.open_todos({"subject": "port the cache", "status": "pending"}), tool_call("MonitorCreate"), SETTLE], classify=answers())
        self.assertEqual(out["classifyCalls"], [])

    def test_the_run_continues_at_most_once_per_run(self):
        out = self.replay([*self.loop(), edit_result(), SETTLE, bash_result("pytest -q", 1, "bad"), SETTLE], classify=answers())
        self.assertTrue(out["results"][4]["continue"])
        self.assertNotIn("continue", out["results"][6])

    def test_a_failing_check_after_the_last_change_makes_fix_the_next_phase_and_continues(self):
        out = self.settle_after(answers(), edit_result(), bash_result("pytest -q", 1, "1 failed"))
        self.assertTrue(out["results"][-1]["continue"])
        self.assertEqual(self.content(out), "next: fix (the anchor exited 1 after the last change)")

    def test_a_loop_with_no_change_yet_never_continues_for_verify_or_review(self):
        # RV-F005: nothing was changed, so no check or review is missing.
        for kind in ("inline", "reviewed"):
            out = self.settle_after(answers(), kind=kind)
            self.assertNotIn("continue", out["results"][-1], kind)
            self.assertIsNone(self.advice(out["results"][-1]), kind)

    def test_a_review_phase_continues_only_while_no_clear_review_follows_the_last_change(self):
        steps = (edit_result(), bash_result("pytest -q", 0, "ok"))
        missing = self.settle_after(answers(), *steps, kind="reviewed")
        self.assertTrue(missing["results"][-1]["continue"])
        self.assertTrue(self.content(missing).startswith("next: review ("))
        reviewed = self.settle_after(answers(), *steps, reviewer("Blocking: P0=0 P1=0"), kind="reviewed")
        self.assertNotIn("continue", reviewed["results"][-1])
        self.assertIsNone(self.advice(reviewed["results"][-1]))

    def test_a_blocking_review_makes_fix_the_next_phase_until_the_code_changes(self):
        out = self.settle_after(answers(), edit_result(), bash_result("pytest -q", 0, "ok"), reviewer("Blocking: P0=0 P1=1"), kind="reviewed")
        self.assertTrue(out["results"][-1]["continue"])
        self.assertEqual(self.content(out), "next: fix (blocking review findings are open)")

    def test_back_and_ask_user_never_continue_the_run(self):
        for move in ("back", "ask-user"):
            out = self.settle_after(answers(move), edit_result())
            self.assertNotIn("continue", out["results"][-1], move)
            self.assertIn("concerns: " + {"back": "earlier evidence does not hold", "ask-user": "needs the user's decision"}[move], self.content(out))

    def test_a_run_is_judged_only_when_the_book_gained_an_entry_since_the_last_judgment(self):
        out = self.replay([*self.loop(), SETTLE, SETTLED, SETTLE, SETTLED, edit_result(), SETTLE], classify=answers())
        self.assertIsNotNone(out["results"][3])
        self.assertIsNone(out["results"][5])
        self.assertIsNotNone(out["results"][8])
        self.assertEqual(len(out["classifyCalls"]), 2)

    def test_an_identical_advisory_is_not_repeated(self):
        out = self.replay([*self.loop(), edit_result(), SETTLE, SETTLED, stage(stage="friction", tried="a", found="b"), SETTLE], classify=answers())
        self.assertIsNotNone(self.advice(out["results"][4]))
        self.assertIsNone(self.advice(out["results"][7]))
        self.assertEqual(len(out["classifyCalls"]), 2)

    def test_book_entries_that_are_not_evidence_do_not_trigger_a_new_judgment(self):
        # Todo updates add `task` entries to the book on every status change; they say nothing new about the work.
        out = self.replay([*self.loop(), edit_result(), SETTLE, SETTLED, todo_update(1, "write the fix", "in_progress"), SETTLE], classify=answers())
        self.assertEqual(len(out["classifyCalls"]), 1)

    def test_a_move_that_flaps_on_unchanged_evidence_sends_the_advisory_once(self):
        # Jev's move alternates between advance and back; the next phase and the findings stay the same.
        plan = [answers("advance", done=0.05), answers("back", done=0.05), answers("advance", done=0.05)]
        out = self.replay([*self.loop(), edit_result(), SETTLE, SETTLED, stage(stage="friction", tried="a", found="b"), SETTLE, SETTLED, stage(stage="friction", tried="c", found="d"), SETTLE], classify=plan)
        self.assertEqual(len(out["classifyCalls"]), 3)
        self.assertIsNotNone(self.advice(out["results"][4]))
        self.assertIsNone(self.advice(out["results"][7]))
        self.assertIsNone(self.advice(out["results"][10]))

    def test_an_advisory_whose_gap_is_reworded_but_whose_next_phase_and_concerns_are_the_same_is_not_repeated(self):
        # The failing check's own output changes between settles, which rewords the gap only through the exit code.
        out = self.replay([*self.loop(), edit_result(), bash_result("pytest -q", 1, "bad"), SETTLE, SETTLED, edit_result(), bash_result("pytest -q", 2, "worse"), SETTLE],
                          classify=answers("advance", done=0.05))
        first, second = out["results"][5], out["results"][9]
        self.assertEqual(self.advice(first), "next: fix (the anchor exited 1 after the last change)\nconcerns: evidence not shown to cover the intent")
        self.assertIsNone(self.advice(second))

    def test_entries_an_earlier_handler_returned_are_kept(self):
        earlier = {"type": "custom", "customType": "x", "data": {}}
        out = self.replay([*self.loop(), edit_result(), {**SETTLE, "payload": {**SETTLE["payload"], "entries": [earlier]}}], classify=answers())
        self.assertEqual(out["results"][4]["entries"][0], earlier)
        self.assertEqual(len(out["results"][4]["entries"]), 3)

    def test_a_second_loop_in_the_same_session_is_judged_too(self):
        # RV-F001: the reopened loop used to share the first loop's book id and its judged count.
        out = self.replay([*self.loop(), edit_result(), SETTLE, SETTLED, stage(stage="close", verdict="abandoned"), todo_create(),
                           stage(stage="kind", kind="inline", intent="second"), SETTLE], classify=answers())
        self.assertEqual(len(out["classifyCalls"]), 2)
        self.assertEqual(out["classifyCalls"][1]["intent"], "second")

    def test_a_full_rating_is_noted_without_a_recheck_after_a_clean_review_that_follows_the_last_change(self):
        out = self.settle_after(answers(review="full"), edit_result(), bash_result("pytest -q", 0, "ok"), reviewer("**Blocking:** P0=0 P1=0"), kind="reviewed")
        result = out["results"][-1]
        self.assertNotIn("continue", result)
        self.assertIsNone(self.advice(result))
        self.assertEqual(result["entries"][0]["data"]["concerns"], [])

    def test_a_full_rating_is_a_concern_when_no_clean_review_follows_the_last_change(self):
        out = self.settle_after(answers(review="full"), edit_result(), kind="reviewed")
        self.assertIn("concerns: needs full independent review", self.content(out))

    def test_a_retry_pair_is_reflected_as_resolved_without_a_call(self):
        out = self.settle_after(answers(), edit_result(), bash_result("pytest -q", 0, "ok"), bash_result("pytest -q", 1, "bad"), bash_result("pytest -q", 0, "ok"))
        # The rerun's friction is auto-recorded and reflected as resolved, so the loop is ready to close.
        self.assertIsNone(self.advice(out["results"][-1]))
        self.assertEqual(out["classifyCalls"][0]["friction"].splitlines()[0], "1 recorded, 1 reflected")

    def test_low_completion_done_and_quality_are_listed_as_concerns(self):
        out = self.settle_after(answers("advance", done=0.05, quality=0.5), edit_result(), bash_result("pytest -q", 0, "ok"))
        text = self.content(out)
        self.assertIn("evidence not shown to cover the intent", text)
        self.assertIn("result below the intent", text)

    def test_a_close_tool_result_carries_the_advisory_without_a_call_to_act(self):
        steps = [*self.loop(), edit_result(),
                 {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}},
                 stage(stage="close", verdict="landed"),
                 tool_result("anchorloop_stage", {"stage": "close", "verdict": "landed"}, "Loop closed (landed)", call_id="c9")]
        out = self.replay(steps, classify=answers())
        result = out["results"][-1]
        self.assertEqual(out["classifyCalls"][0]["intent"], "fix the export")
        self.assertEqual(self.book_files(), [])
        # Closing with no concern says nothing more than the close result.
        self.assertIsNone(result)

    def test_a_close_tool_result_carries_only_jevs_concerns(self):
        steps = [*self.loop(), edit_result(),
                 {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}},
                 stage(stage="close", verdict="landed"),
                 tool_result("anchorloop_stage", {"stage": "close", "verdict": "landed"}, "closed (landed).", call_id="c9")]
        result = self.replay(steps, classify=answers("advance", done=0.05, review="full"))["results"][-1]
        self.assertEqual(result["content"][0]["text"], "closed (landed).")
        self.assertEqual(result["content"][1]["text"], "\nJev: evidence not shown to cover the intent; needs full independent review.")

    def test_a_refused_close_is_not_judged(self):
        todos = todo_state({"subject": "x", "status": "pending"})
        steps = [*self.loop(), {"branchAdd": [todos]},
                 {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}},
                 tool_result("anchorloop_stage", {"stage": "close"}, "refused", call_id="c9", isError=True)]
        out = self.replay(steps, classify=answers())
        self.assertIsNone(out["results"][-1])
        self.assertEqual(out["classifyCalls"], [])

    def test_failure_records_unknown_and_continues_nothing(self):
        result = self.settle_after("throw", edit_result())["results"][-1]
        self.assertEqual(result["entries"][0]["data"], {"verdict": "unknown", "reason": "network down"})
        self.assertNotIn("continue", result)

    def test_without_a_key_or_a_classifier_nothing_is_asked_or_recorded(self):
        for plan in ("no-auth", "missing"):
            out = self.settle_after(plan)
            self.assertIsNone(out["results"][-1], plan)
            self.assertEqual(out["classifyCalls"], [], plan)

    def test_a_run_that_arranged_a_wake_is_not_judged(self):
        for tool in ("MonitorCreate", "subagent"):
            out = self.replay([*self.loop(), tool_call(tool), SETTLE], classify=answers())
            self.assertIsNone(out["results"][-1], tool)
            self.assertEqual(out["classifyCalls"], [], tool)

    def test_a_subagent_session_is_never_judged(self):
        markers = [{"PI_SUBAGENT_ID": "child-1"}, {"PI_SUBAGENT_CHILD": "1"},
                   {"PI_SUBAGENT_CHILD_AGENT": "worker", "PI_SUBAGENT_PARENT_PID": "42"}]
        for env in markers:
            out = self.replay([*self.loop(), SETTLE], classify=answers("back", 0.1, "full", 0), env=env)
            self.assertIsNone(out["results"][-1], env)
            self.assertEqual(out["classifyCalls"], [], env)

    def test_a_quick_loop_is_never_judged(self):
        steps = [user_start(), todo_create(), stage(stage="kind", kind="quick", intent="a typo", anchor="make lint"), edit_result(),
                 {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}}]
        out = self.replay([*steps, SETTLE], classify=answers())
        self.assertIsNone(out["results"][-1])
        self.assertEqual(out["classifyCalls"], [])

    def test_a_book_that_cannot_be_read_never_blocks_the_settle(self):
        blocker = self.cwd.parent / "not-a-dir"
        blocker.write_text("x")
        out = self.replay([*self.loop(), SETTLE], classify=answers(), env={"ANCHORLOOP_BOOKS_DIR": str(blocker)})
        self.assertIsNone(out["results"][-1])


def edit_result(path: str = "src/app.py") -> dict:
    return tool_result("write", {"path": path})


def reviewer(text: str) -> dict:
    message = {"role": "custom", "customType": "subagent_result", "details": {"agent": "reviewer", "name": "r", "resultContent": text}}
    return {"event": "message_end", "payload": {"message": message}}


def answers(move: str = "advance", done: float = 0.9, review: str = "none", quality: float = 2.9) -> dict:
    return {
        "stopReason": "stop",
        "answers": {
            "move": {"type": "choice", "choice": move, "probabilities": {move: 0.7}},
            "done": {"type": "bool", "probability": done},
            "review": {"type": "choice", "choice": review, "probabilities": {review: 0.6}, "confidence": 0.4},
            "quality": {"type": "score", "score": quality, "confidence": 0.5},
        },
    }


if __name__ == "__main__":
    unittest.main()
