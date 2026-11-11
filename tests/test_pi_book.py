"""The loop book: opening on todo create, stages with attached evidence, durable artifacts, closing, sweeping."""

import json
import os
import subprocess
import unittest
from pathlib import Path

from tests.pi_harness import (
    ExtensionCase,
    bash_result,
    stage,
    todo_create,
    todo_state,
    todo_update,
    tool_result,
)


def reviewer_result(text: str, agent: str = "reviewer") -> dict:
    message = {"role": "custom", "customType": "subagent_result", "details": {"name": "r1", "agent": agent, "resultContent": text}}
    return {"event": "message_end", "payload": {"message": message}}


def text_of(result: dict) -> str:
    return "\n".join(block["text"] for block in result["content"])


def answers(**probabilities: float) -> dict:
    return {"stopReason": "stop", "answers": {name: {"type": "bool", "probability": value} for name, value in probabilities.items()}}


def subagent_result(agent: str, name: str, text: str, task: str = "") -> dict:
    message = {"role": "custom", "customType": "subagent_result", "details": {"name": name, "agent": agent, "resultContent": text, "task": task}}
    return {"event": "message_end", "payload": {"message": message}}


def edit(path: str = "src/app.py") -> dict:
    return tool_result("write", {"path": path})


class BookCase(ExtensionCase):
    extension = "book.ts"

    def open_loop(self, kind: str = "inline", intent: str = "fix the export", anchor: str | None = None) -> list[dict]:
        extra = {"anchor": anchor} if anchor else {}
        # `kind` first: a todo create opens the loop as inline on its own, and these tests choose the kind themselves.
        return [stage(stage="kind", kind=kind, intent=intent, **extra), todo_create()]

    def entries(self, name: str, which: Path | None = None) -> list[dict]:
        return [entry for entry in self.book(which)[1] if entry["stage"] == name]

    def read_text(self, steps: list[dict], **kwargs) -> str:
        """The `read` output after replaying `steps` in one Node run."""
        out = self.replay([*steps, stage(stage="read")], **kwargs)
        return text_of(out["results"][-1])


class TestLifecycle(BookCase):
    def test_nothing_is_recorded_without_a_loop(self):
        out = self.replay([stage(stage="read"), stage(stage="friction", tried="a", found="b")])
        self.assertIn("No loop is open", text_of(out["results"][0]))
        self.assertIn("No loop is open", text_of(out["results"][1]))
        self.assertEqual(self.book_files(), [])

    def test_kind_opens_the_loop_itself_when_a_todo_create_in_the_same_batch_has_not_landed(self):
        out = self.replay([stage(stage="kind", kind="inline", intent="x", anchor="pytest"), todo_create(), stage(stage="read")])
        self.assertEqual(text_of(out["results"][0]), "ok")
        self.assertEqual(len(self.book_files()), 1)
        self.assertEqual([e["stage"] for e in self.book()[1]], ["kind", "anchor", "task"])
        self.assertIsNone(out["results"][1])
        self.assertTrue(text_of(out["results"][2]).startswith("inline · phase anchor ✓ → act"))

    def test_a_kind_call_that_cannot_open_a_loop_creates_no_book(self):
        out = self.replay([stage(stage="kind", kind="inline")])
        self.assertIn("intent", out["results"][0]["error"])
        self.assertEqual(self.book_files(), [])

    def test_the_first_todo_create_opens_an_inline_loop_and_says_nothing_about_it(self):
        out = self.replay([todo_create("first"), todo_create("second", task_id=2)])
        self.assertEqual([result for result in out["results"] if result], [])
        self.assertEqual(len(self.book_files()), 1)
        header, entries = self.book()
        self.assertEqual((header["owner"], header["session"], [e["stage"] for e in entries]), ("main", str(self.session_file), ["kind", "task", "task"]))
        kind = entries[0]
        self.assertEqual((kind["kind"], kind["intent"]), ("inline", "first"))

    def test_the_first_todo_subject_is_the_intent_cut_to_a_line(self):
        self.replay([todo_create("fix\nthe   export " + "x" * 400)])
        intent = self.entries("kind")[0]["intent"]
        self.assertTrue(intent.startswith("fix the export x"))
        self.assertLessEqual(len(intent), 200)

    def test_the_first_todos_anchor_metadata_is_the_loop_anchor(self):
        self.replay([todo_create("first", anchor="pytest -q")])
        self.assertEqual([entry["check"] for entry in self.entries("anchor")], ["pytest -q"])

    def test_a_reality_anchor_line_stated_before_the_todo_is_the_loop_anchor_and_beats_the_metadata(self):
        branch = [{"type": "message", "message": {"role": "user", "content": "fix it"}},
                  {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest tests/test_export.py"}]}}]
        self.replay([todo_create("first", anchor="make test")], branch=branch)
        self.assertEqual([entry["check"] for entry in self.entries("anchor")], ["pytest tests/test_export.py"])

    def test_the_default_inline_loop_can_choose_another_kind_without_a_reason(self):
        out = self.replay([todo_create("first"), stage(stage="kind", kind="reviewed"), stage(stage="kind", kind="durable")])
        self.assertEqual(text_of(out["results"][1]), "ok")
        self.assertIn("reason", out["results"][2]["error"])

    def test_todo_calls_other_than_create_do_not_open_a_loop(self):
        self.replay([tool_result("todo", {"action": "list"}), tool_result("todo", {"action": "update", "id": 1})])
        self.assertEqual(self.book_files(), [])

    def test_a_second_kind_declaration_upgrades_the_open_loop(self):
        out = self.replay([*self.open_loop("inline"), stage(stage="kind", kind="reviewed", reason="the fix reaches a shared reader"), stage(stage="read")])
        self.assertEqual(len(self.book_files()), 1)
        self.assertEqual(text_of(out["results"][2]), "ok")
        self.assertTrue(text_of(out["results"][3]).startswith("reviewed · phase start → anchor"))
        self.assertIn("intent: fix the export", text_of(out["results"][3]))
        self.assertEqual(self.stages(), ["kind", "kind"])

    def test_the_kind_call_carries_the_anchor_command_and_a_later_call_sets_it_again(self):
        self.replay([*self.open_loop("inline", anchor="pytest -q"), stage(stage="kind", anchor="make test")])
        anchors = self.entries("anchor")
        self.assertEqual([a["check"] for a in anchors], ["pytest -q", "make test"])
        self.assertEqual(len(self.entries("kind")), 1)

    def test_a_kind_call_without_a_loop_needs_a_kind_and_an_intent(self):
        out = self.replay([stage(stage="kind", kind="quick"), stage(stage="kind", intent="x"), stage(stage="kind")])
        self.assertIn("intent", out["results"][0]["error"])
        self.assertIn("kind", out["results"][1]["error"])
        self.assertIn("needs", out["results"][2]["error"])
        self.assertEqual(self.book_files(), [])

    def test_a_kind_call_with_only_an_anchor_extends_the_default_loop(self):
        out = self.replay([todo_create(), stage(stage="kind", anchor="make test")])
        self.assertEqual(text_of(out["results"][1]), "ok")
        self.assertEqual([entry["check"] for entry in self.entries("anchor")], ["make test"])

    def test_declarations_the_program_can_observe_are_not_accepted(self):
        out = self.replay([*self.open_loop(), *[stage(stage=name) for name in ("act", "check", "review", "anchor", "decision", "spec", "design")]])
        for result in out["results"][2:]:
            self.assertIn("unknown stage", result["error"])
        self.assertEqual(self.stages(), ["kind"])

    def test_close_refuses_while_a_todo_lacks_a_disposition_and_lists_it(self):
        todos = todo_state(
            {"subject": "ship it", "status": "in_progress"},
            {"subject": "ticketed", "status": "pending", "metadata": {"followup": "MP-12"}},
            {"subject": "vague", "status": "pending", "metadata": {"followup": "later"}},
            {"subject": "done", "status": "completed"},
        )
        out = self.replay([*self.open_loop(), {"branchAdd": [todos]}, stage(stage="close", verdict="landed")])
        error = out["results"][3]["error"]
        self.assertIn("#1 ship it", error)
        self.assertIn("#3 vague", error)
        self.assertNotIn("ticketed", error)
        self.assertNotIn("done", error)
        self.assertEqual(len(self.book_files()), 1)
        self.assertEqual(out["appended"], [])

    def test_close_records_one_session_entry_and_deletes_the_book_and_its_children(self):
        child = self.books / "x" / "agents" / "kid.yml"
        child.parent.mkdir(parents=True)
        child.write_text('id: "kid"\nsession: null\nentries:\n')
        todos = todo_state(
            {"subject": "a", "status": "pending", "metadata": {"followup": "MP-12"}},
            {"subject": "b", "status": "pending", "metadata": {"followup": "memory"}},
            {"subject": "c", "status": "in_progress", "metadata": {"followup": "drop — superseded"}},
        )
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "w", "agent": "worker", "status": "started"})
        out = self.replay([*self.open_loop(anchor="pytest -q"), link, {"branchAdd": [todos]}, stage(stage="close", verdict="landed")])
        self.assertTrue(text_of(out["results"][-1]).startswith("closed (landed)."))
        self.assertTrue(text_of(out["results"][-1]).endswith("Clear the todo list."))
        self.assertEqual(self.book_files(), [])
        self.assertFalse(child.exists())
        (entry,) = out["appended"]
        self.assertEqual(entry["customType"], "anchorloop-loop")
        data = entry["data"]
        self.assertEqual((data["intent"], data["kind"], data["verdict"]), ("fix the export", "inline", "landed"))
        self.assertEqual(data["stages"], ["kind", "anchor"])
        self.assertEqual(data["reviewRounds"], 0)
        self.assertEqual([f["followup"] for f in data["followups"]], ["MP-12", "memory", "drop — superseded"])

    def test_a_new_loop_can_open_once_the_old_one_is_closed_and_gets_its_own_id(self):
        self.replay(self.open_loop())
        first = self.book()[0]["id"]
        self.replay([stage(stage="close", verdict="abandoned")])
        self.assertEqual(self.book_files(), [])
        self.replay([todo_create()])
        second = self.book()[0]["id"]
        self.assertNotEqual(first, second)
        self.assertTrue(second.startswith("sess-1-"))

    def test_read_summarizes_the_phase_line_intent_check_reviews_and_friction(self):
        text = self.read_text([*self.open_loop(anchor="pytest -q")])
        lines = text.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "inline · phase anchor ✓ → act (missing: a change to the code)")
        self.assertEqual(lines[1], "intent: fix the export")
        self.assertEqual(lines[2], "last verify: none")
        self.assertEqual(lines[3], "reviews: no review; open todos: 0; friction: 0 (0 unreflected)")


class TestToolSchemas(BookCase):
    """The tool schemas ride along on every turn of every session, so their size is a budget."""

    def schemas(self) -> dict:
        return self.replay([], extensions=("book.ts", "decision-tool.ts"))["schemas"]

    def test_the_stage_tool_description_stays_near_150_tokens_and_keeps_its_required_fields_and_enums(self):
        stage_tool = self.schemas()["anchorloop_stage"]
        self.assertLessEqual(len(stage_tool["description"]) / 4, 150)
        parameters = stage_tool["parameters"]
        self.assertEqual(parameters["required"], ["stage"])
        self.assertEqual(parameters["properties"]["stage"]["enum"], ["kind", "verify", "fresh-read", "friction", "reflect", "skip", "back", "landed", "close", "read"])
        self.assertEqual(parameters["properties"]["kind"]["enum"], ["quick", "inline", "reviewed", "durable"])
        self.assertEqual(parameters["properties"]["verdict"]["enum"], ["landed", "blocked", "abandoned"])
        self.assertEqual(parameters["properties"]["class"]["enum"], ["misdirection", "gap", "resolved"])
        self.assertLessEqual(len(json.dumps(stage_tool)) / 4, 460)

    def test_the_decision_tool_description_stays_near_60_tokens_and_names_what_a_row_is_for(self):
        decision_tool = self.schemas()["anchorloop_decision"]
        self.assertLessEqual(len(decision_tool["description"]) / 4, 60)
        self.assertIn("fork, pivot, or blocker", decision_tool["description"])
        self.assertIn("git log", decision_tool["description"])
        self.assertEqual(decision_tool["parameters"]["required"], ["log"])


class TestEvidence(BookCase):
    def test_a_bash_call_that_runs_the_anchor_command_records_its_exit_code_and_last_line(self):
        self.replay([
            *self.open_loop(anchor="pytest -q"),
            bash_result("cd tests && pytest -q", 1, "collected 3\n1 failed\n"),
            bash_result("ls", 0, "files\n"),
            bash_result("pytest -q", 0, "3 passed\n"),
        ])
        runs = self.entries("verify")
        self.assertEqual([(e["exit"], e["last"]) for e in runs], [(1, "1 failed"), (0, "3 passed")])

    def test_a_loop_without_an_anchor_command_records_no_runs(self):
        self.replay([*self.open_loop(), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.stages(), ["kind"])

    def test_a_quick_loop_and_a_child_record_runs_as_check(self):
        self.replay([*self.open_loop("quick", anchor="make lint"), bash_result("make lint", 2, "2 errors\n")])
        self.assertEqual([(e["exit"], e["last"]) for e in self.entries("check")], [(2, "2 errors")])
        env = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w", "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay([*self.open_loop("inline", anchor="pytest"), bash_result("pytest", 0, "5 passed")], env=env)
        child = next(self.books.rglob("kid.yml"))
        self.assertEqual(self.stages(child), ["kind", "anchor", "check"])

    def test_the_exit_code_falls_back_to_the_error_flag_and_the_message_when_structured_content_is_gone(self):
        def raw(command: str, content: str, is_error: bool) -> dict:
            return tool_result("bash", {"command": command}, content, isError=is_error)

        self.replay([*self.open_loop(anchor="pytest"), raw("pytest a", "fine", False), raw("pytest b", "boom\n\nCommand exited with code 3", True), raw("pytest c", "timed out", True)])
        self.assertEqual([e["exit"] for e in self.entries("verify")], [0, 3, "unknown"])

    def test_a_declared_verify_covers_an_anchor_that_is_not_a_command_and_is_refused_for_a_command(self):
        out = self.replay([*self.open_loop(), stage(stage="verify"), stage(stage="verify", note="the page renders the new column")])
        self.assertIn("note", out["results"][2]["error"])
        (verify,) = self.entries("verify")
        self.assertEqual((verify["declared"], verify["result"], verify["exit"]), (True, "pass", 0))

    def test_a_declared_verify_is_accepted_for_a_command_anchor_and_a_later_failing_run_overrides_it(self):
        # RV2-F001
        out = self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="verify", note="looked fine"), bash_result("pytest -q", 1, "1 failed")])
        self.assertNotIn("error", out["results"][2])
        self.assertEqual([(e.get("declared"), e["exit"]) for e in self.entries("verify")], [(True, 0), (None, 1)])

    def test_an_anchor_run_piped_on_records_an_unknown_exit(self):
        # RV2-F004
        self.replay([*self.open_loop(anchor="pytest -q"), bash_result("pytest -q 2>&1 | tail -3", 0, "2 failed, 10 passed")])
        self.assertEqual([e["exit"] for e in self.entries("verify")], ["unknown"])

    def test_a_production_edit_is_recorded_once_per_burst_and_other_files_are_not(self):
        self.replay([*self.open_loop(), edit("src/a.py"), edit("src/b.py"), edit("README.md"), edit("scratch/x.py"), edit("docs/specs/2026-10-29-x/notes.md")])
        self.assertEqual(self.stages(), ["kind", "edit"])
        self.assertEqual(self.entries("edit")[0]["path"], "src/a.py")

    def test_an_edit_after_a_run_starts_a_new_burst(self):
        self.replay([*self.open_loop(anchor="pytest"), edit(), bash_result("pytest", 0, "ok"), edit()])
        self.assertEqual(self.stages(), ["kind", "anchor", "edit", "verify", "edit"])

    def test_a_failed_write_records_nothing(self):
        self.replay([*self.open_loop(), tool_result("write", {"path": "src/a.py"}, isError=True)])
        self.assertEqual(self.stages(), ["kind"])

    def test_a_first_commit_counts_as_the_change_when_no_write_or_edit_was_seen(self):
        self.git_repo()
        self.replay(self.open_loop())
        (self.cwd / "app.py").write_text("print(1)\nprint(2)\n")
        self.replay([bash_result("git commit -am wip", 0, "[main abc] wip")])
        self.assertEqual(self.entries("edit")[0]["via"], "commit")
        self.replay([bash_result("git commit -am again", 0, "ok")])
        self.assertEqual(len(self.entries("edit")), 1)

    def test_the_diff_is_taken_against_the_base_head_of_each_repo(self):
        self.git_repo()
        other = self.cwd.parent / "other"
        other.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(other), *args], check=True, capture_output=True)
        (other / "lib.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(other), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "base"], check=True, capture_output=True)
        steps = [*self.open_loop(), {"event": "tool_call", "payload": {"toolName": "edit", "toolCallId": "e1", "input": {"path": str(other / "lib.py")}}}]
        self.replay(steps)
        (self.cwd / "app.py").write_text("print(1)\nprint(2)\n")
        (other / "lib.py").write_text("x = 2\ny = 3\n")
        out = self.replay([stage(stage="close", verdict="abandoned")])
        (entry,) = out["appended"]
        diff = entry["data"]["diff"]
        self.assertIn("work: 1 file changed", diff)
        self.assertIn("other: 1 file changed", diff)

    def test_a_repo_is_added_once_at_its_first_touch(self):
        self.git_repo()
        call = {"event": "tool_call", "payload": {"toolName": "write", "toolCallId": "e1", "input": {"path": "app.py"}}}
        self.replay([*self.open_loop(), call, call])
        self.assertEqual(self.stages().count("base"), 1)
        self.assertEqual(self.entries("base")[0]["head"], subprocess.run(["git", "-C", str(self.cwd), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())


class TestReview(BookCase):
    def rounds(self) -> list[dict]:
        return self.entries("review")

    def test_each_reviewer_result_becomes_one_round_with_its_blocking_line_counts(self):
        out = self.replay([
            *self.open_loop("reviewed"),
            reviewer_result("Findings...\n\n**Blocking:** P0=0 P1=2\n"),
            reviewer_result("Round two.\nBlocking: P0=0 P1=1"),
            reviewer_result("Clean.\n**Blocking: P0=0 P1=0**"),
        ])
        self.assertEqual([(e["round"], e["p0"], e["p1"], e["blocking"]) for e in self.rounds()], [(1, 0, 2, True), (2, 0, 1, True), (3, 0, 0, False)])
        warned = [notice["step"] for notice in out["notices"]]
        self.assertEqual(warned, [3])
        self.assertIn("hand the trend to the user", out["notices"][0]["message"])
        self.assertEqual(out["notices"][0]["level"], "warning")

    def test_a_round_is_never_reused_without_a_newer_reviewer_result(self):
        # RV-F002: the old design let a later review declaration reuse the earlier result's counts.
        steps = [*self.open_loop("reviewed", anchor="pytest"), edit(), bash_result("pytest", 0, "ok"), reviewer_result("Blocking: P0=0 P1=2"), edit(), bash_result("pytest", 0, "ok")]
        text = self.read_text(steps)
        self.assertEqual(len(self.rounds()), 1)
        self.assertIn("→ review (missing: a review round after the last change", text)
        self.assertNotIn("hand the trend", text)

    def test_a_reviewer_result_that_arrives_before_the_loop_opens_is_not_recorded(self):
        self.replay([reviewer_result("Blocking: P0=0 P1=1"), *self.open_loop("reviewed")])
        self.assertEqual(self.rounds(), [])

    def test_an_adversarial_reviewer_counts_and_other_agents_do_not(self):
        self.replay([*self.open_loop("reviewed"), reviewer_result("Blocking: P0=1 P1=0", "worker"), reviewer_result("Blocking: P0=0 P1=3", "adversarial-reviewer")])
        (only,) = self.rounds()
        self.assertEqual(only["p1"], 3)

    def test_without_a_blocking_line_jev_answers_whether_findings_block(self):
        out = self.replay([*self.open_loop("reviewed"), reviewer_result("found a P1 race in the cache")], classify=answers(blocking=0.9))
        (round_,) = self.rounds()
        self.assertEqual((round_["blocking"], round_["source"]), (True, "jev"))
        self.assertEqual(out["classifyCalls"], [{"review": "found a P1 race in the cache"}])

    def test_without_a_blocking_line_or_a_jev_key_the_finding_state_is_unknown(self):
        self.replay([*self.open_loop("reviewed"), reviewer_result("looks fine")], classify="no-auth")
        self.assertIsNone(self.rounds()[0]["blocking"])

    def test_a_failed_cancelled_or_incomplete_reviewer_result_is_never_a_clear_round(self):
        # RV2-F002
        def failed(**details) -> dict:
            message = {"role": "custom", "customType": "subagent_result", "details": {"name": "r1", "agent": "reviewer", "resultContent": "Blocking: P0=0 P1=0", **details}}
            return {"event": "message_end", "payload": {"message": message}}

        out = self.replay([
            *self.open_loop("reviewed"),
            failed(error="cancelled"), failed(errorMessage="boom"), failed(exitCode=1),
            reviewer_result("**Status:** INCOMPLETE\n\nBlocking: P0=0 P1=0"),
        ], classify=answers(blocking=0.1))
        self.assertEqual([(e["blocking"], e["source"]) for e in self.rounds()], [(None, "failed")] * 4)
        self.assertEqual(out["classifyCalls"], [])

    def test_only_the_main_session_records_reviews(self):
        env = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w", "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay([*self.open_loop(), reviewer_result("Blocking: P0=0 P1=0")], env=env)
        self.assertEqual(self.stages(next(self.books.rglob("kid.yml"))), ["kind"])


class TestChildren(BookCase):
    ENV = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "worker-1"}

    def child_env(self) -> dict:
        return {**self.ENV, "PI_SUBAGENT_SESSION": str(self.session_file)}

    def child(self, *more: dict) -> None:
        self.replay([*self.open_loop("inline", "child work", anchor="pytest"), bash_result("pytest", 0, "5 passed"), *more], env=self.child_env())

    link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "worker-1", "agent": "worker", "status": "started"})

    def test_main_links_a_child_when_the_subagent_result_returns_its_id_and_read_shows_its_checks(self):
        self.child()
        out = self.replay([*self.open_loop(), self.link, stage(stage="read")])
        self.assertIn("child worker-1: inline; stages kind, anchor, check; check exit 0: 5 passed", text_of(out["results"][3]))
        main = next(path for path in self.book_files() if path.parent.name != "agents")
        self.assertIn("link", self.stages(main))

    def test_a_child_that_closes_keeps_its_book_for_main_and_main_deletes_it_on_close(self):
        self.child(stage(stage="close", verdict="landed"))
        kid = next(self.books.rglob("kid.yml"))
        self.assertEqual(self.entries("close", kid)[0]["verdict"], "landed")
        out = self.replay([*self.open_loop(), self.link, stage(stage="read")])
        self.assertIn("child worker-1: inline (closed); stages kind, anchor, check", text_of(out["results"][3]))
        self.replay([stage(stage="close", verdict="landed")])
        self.assertFalse(kid.exists())

    def test_a_closed_child_book_is_no_open_loop_and_a_new_todo_opens_a_fresh_one(self):
        self.child(stage(stage="close", verdict="landed"))
        out = self.replay([stage(stage="read")], env=self.child_env())
        self.assertIn("No loop is open", text_of(out["results"][0]))
        self.replay([todo_create("again")], env=self.child_env())
        kid = next(self.books.rglob("kid.yml"))
        self.assertEqual([entry["stage"] for entry in self.book(kid)[1]], ["kind", "task"])

    def test_a_childs_friction_shows_in_main_read_under_its_name(self):
        self.child(stage(stage="friction", tried="ran the old command", found="it was renamed", led_by="skill X"))
        out = self.replay([*self.open_loop(), self.link, stage(stage="read")])
        text = text_of(out["results"][3])
        self.assertIn("friction worker-1#1: ran the old command → it was renamed", text)
        self.assertIn("friction: 1 (1 unreflected)", text)


class TestFriction(BookCase):
    def test_friction_entries_are_numbered_and_need_tried_and_found(self):
        out = self.replay([*self.open_loop(), stage(stage="friction", tried="a"), stage(stage="friction", tried="a", found="b", led_by="skill X"),
                           stage(stage="friction", tried="c", found="d")])
        self.assertIn("tried", out["results"][2]["error"])
        first, second = self.entries("friction")
        self.assertEqual((first["id"], first["led_by"], second["id"], second["led_by"]), (1, "skill X", 2, "none"))

    def test_reflect_covers_friction_ids_with_a_class_and_rejects_unknown_ids(self):
        out = self.replay([*self.open_loop(), stage(stage="friction", tried="a", found="b"), stage(stage="reflect", friction=[1, 9], **{"class": "gap"}),
                           stage(stage="reflect", friction=[1], **{"class": "gap", "action": "solid-loop"}), stage(stage="reflect", friction=[1])])
        self.assertIn("unknown friction 9", out["results"][3]["error"])
        self.assertIn("class", out["results"][5]["error"])
        (reflect,) = self.entries("reflect")
        self.assertEqual((reflect["friction"], reflect["class"], reflect["action"]), (["1"], "gap", "solid-loop"))

    def test_a_failed_anchor_run_followed_by_a_pass_records_its_own_friction(self):
        steps = [*self.open_loop(anchor="pytest"), edit(), bash_result("pytest", 0, "ok"), edit(), bash_result("pytest", 1, "1 failed"), edit(), bash_result("pytest", 0, "ok")]
        self.assertIn("friction: 1 (0 unreflected)", self.read_text(steps))

    def test_red_first_failures_before_any_pass_are_not_retries(self):
        steps = [*self.open_loop(anchor="pytest"), bash_result("pytest", 1, "1 failed"), bash_result("pytest", 1, "1 failed"), bash_result("pytest", 0, "ok")]
        self.assertIn("friction: 0 (0 unreflected)", self.read_text(steps))

    def test_a_task_anchor_run_counts_for_retry_pairs(self):
        steps = [todo_create("t", anchor="pytest -q x"), stage(stage="kind", kind="inline", intent="x"), bash_result("pytest -q x", 0, "ok"), bash_result("pytest -q x", 1, "bad"), bash_result("pytest -q x", 0, "ok")]
        self.assertIn("friction: 1 (0 unreflected)", self.read_text(steps))

    def test_close_never_refuses_over_friction_carries_it_into_the_session_entry_and_lists_the_unreflected(self):
        out = self.replay([*self.open_loop(), stage(stage="friction", tried="a", found="b", led_by="skill X"), stage(stage="friction", tried="c", found="d"),
                           stage(stage="reflect", friction=[1], **{"class": "misdirection", "action": "solid-loop"}), stage(stage="close", verdict="landed")])
        text = text_of(out["results"][-1])
        self.assertTrue(text.startswith("closed (landed)."), text)
        self.assertIn("unreflected friction: 2 (d)", text)
        self.assertNotIn("1 (b)", text)
        (entry,) = out["appended"]
        friction = entry["data"]["friction"]
        self.assertEqual([(f["ref"], f["class"], f["action"], f["led_by"]) for f in friction], [("1", "misdirection", "solid-loop", "skill X"), ("2", None, None, "none")])

    def test_a_reflect_in_main_covers_a_childs_friction(self):
        env = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "worker-1", "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay([*self.open_loop("inline", "child"), stage(stage="friction", tried="a", found="b")], env=env)
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "worker-1", "agent": "worker", "status": "started"})
        out = self.replay([*self.open_loop(), link, stage(stage="reflect", friction=["worker-1#1"], **{"class": "resolved"}), stage(stage="read")])
        self.assertIn("friction worker-1#1: a → b [resolved]", text_of(out["results"][4]))
        self.assertIn("friction: 1 (0 unreflected)", text_of(out["results"][4]))


class TestDurableArtifacts(BookCase):
    def write(self, name: str, text: str) -> dict:
        path = self.cwd / "docs" / "specs" / "2026-10-29-x" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return tool_result("write", {"path": f"docs/specs/2026-10-29-x/{name}"})

    def entries(self, stage_name: str) -> list[dict]:
        return [entry for entry in self.book()[1] if entry["stage"] == stage_name and entry.get("auto")]

    def test_decision_edits_record_row_counts_and_the_questions_whose_status_changed(self):
        table = "| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which db? | pg | req | grounded |\n| Cache? | | | open |\n"
        self.replay([*self.open_loop("durable"), self.write("decision.md", table)])
        self.replay([self.write("decision.md", table.replace("| | | open |", "| yes | user | confirmed |"))])
        self.replay([self.write("decision.md", table.replace("| | | open |", "| yes | user | confirmed |") + "| Auth? | | | open |\n")])
        first, second, third = self.entries("decision")
        self.assertEqual(first["counts"], {"grounded": 1, "confirmed": 0, "open": 1})
        self.assertEqual(first["changed"], ["Which db?", "Cache?"])
        self.assertEqual(second["counts"], {"grounded": 1, "confirmed": 1, "open": 0})
        self.assertEqual(second["changed"], ["Cache?"])
        self.assertEqual((third["counts"]["open"], third["changed"]), (1, ["Auth?"]))

    def test_spec_edits_record_the_status_and_the_headings_whose_text_changed(self):
        text = "Status: proposed\n\n# Spec\n\n## Behavior\n\nA.\n\n## Edge cases\n\nB.\n"
        self.replay([*self.open_loop("durable"), self.write("spec.md", text)])
        self.replay([self.write("spec.md", text.replace("proposed", "approved").replace("A.", "A2."))])
        first, second = self.entries("spec")
        self.assertEqual(first["status"], "proposed")
        self.assertEqual(sorted(first["changed"]), ["Behavior", "Edge cases", "Spec"])
        self.assertEqual(second["status"], "approved")
        self.assertIn("Behavior", second["changed"])
        self.assertNotIn("Edge cases", second["changed"])

    def test_design_and_verification_record_changed_headings_and_result_counts(self):
        design = "## Approach\n\nX.\n\n## Risks\n\nY.\n"
        table = "# Verification\n\n| Requirement | Evidence | Result |\n|---|---|---|\n| a | ran | pass |\n| b | ran | fail |\n| c | - | unknown |\n"
        self.replay([*self.open_loop("durable"), self.write("design.md", design), self.write("verification.md", table)])
        self.replay([self.write("design.md", design.replace("Y.", "Z."))])
        _, d2 = self.entries("design")
        self.assertEqual(d2["changed"], ["Risks"])
        self.assertEqual(self.entries("verification")[0]["counts"], {"pass": 1, "fail": 1, "unknown": 1})

    def test_the_spec_entry_records_whether_it_names_an_approval_and_the_design_entry_whether_its_approach_is_filled(self):
        spec = "Status: approved\nApproved from: user 2026-10-29\n\n# Spec\n"
        self.replay([*self.open_loop("durable"), self.write("spec.md", spec), self.write("design.md", "## Approach\n\n## Risks\n\nY.\n")])
        self.replay([self.write("design.md", "## Approach\n\nUse X.\n")])
        self.assertEqual(self.entries("spec")[0]["approvedFrom"], True)
        self.assertEqual([entry["approach"] for entry in self.entries("design")], [False, True])
        self.replay([self.write("spec.md", "Status: approved\n\n# Spec\n")])
        self.assertEqual(self.entries("spec")[-1]["approvedFrom"], False)

    def test_edits_to_other_files_or_outside_a_loop_record_nothing(self):
        self.replay([tool_result("write", {"path": "docs/specs/2026-10-29-x/notes.md"}), self.write("spec.md", "Status: proposed\n")])
        self.assertEqual(self.book_files(), [])
        self.replay([*self.open_loop(), tool_result("write", {"path": "docs/specs/2026-10-29-x/notes.md"})])
        self.assertEqual(self.stages(), ["kind"])


class TestTodoLinks(BookCase):
    SPEC = "Status: proposed\n\n# Spec\n\n## Behavior\n\nA.\nB.\n\n## Edge\n\nC.\n"
    REF = "docs/specs/2026-10-29-x/spec.md"

    def spec(self, text: str) -> None:
        path = self.cwd / self.REF
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def tasks(self) -> list[dict]:
        return [entry for entry in self.book()[1] if entry["stage"] == "task"]

    def test_create_and_update_record_task_entries_with_anchor_resolved_refs_and_followup(self):
        self.spec(self.SPEC)
        refs = [f"{self.REF}#Behavior", f"{self.REF}#Gone"]
        self.replay([todo_create("build it", anchor="pytest -q tests/x", ref=refs, followup="MP-9"),
                     todo_update(1, "build it", "in_progress", anchor="pytest -q tests/x", ref=refs[:1])])
        first, second = self.tasks()
        self.assertEqual((first["id"], first["subject"], first["status"], first["anchor"], first["followup"]),
                         (1, "build it", "pending", "pytest -q tests/x", "MP-9"))
        self.assertEqual(first["refs"], [{"ref": refs[0], "range": "L5-L8"}, {"ref": refs[1], "range": "missing"}])
        self.assertEqual((second["status"], len(second["refs"])), ("in_progress", 1))

    def test_a_task_without_anchor_or_ref_is_recorded_as_is_without_a_warning(self):
        out = self.replay([todo_create("plain"), stage(stage="kind", kind="durable", intent="x")])
        (entry,) = self.tasks()
        self.assertEqual(set(entry), {"ts", "stage", "id", "subject", "status"})
        self.assertIsNone(out["results"][0])
        self.assertEqual(out["notices"], [])

    def test_a_todo_update_outside_a_loop_opens_nothing(self):
        self.replay([todo_update(1, "x", "completed")])
        self.assertEqual(self.book_files(), [])

    def test_read_lists_tasks_with_anchor_exit_code_and_refs_re_resolved_at_read(self):
        self.spec(self.SPEC)
        ref = f"{self.REF}#Behavior"
        todos = todo_state({"subject": "build it", "status": "in_progress", "metadata": {"anchor": "pytest -q", "ref": ref}},
                           {"subject": "plain", "status": "pending"})
        self.replay([todo_create("build it", anchor="pytest -q", ref=ref), todo_create("plain", task_id=2),
                     stage(stage="kind", kind="inline", intent="x"), bash_result("cd t && pytest -q", 1, "1 failed")])
        out = self.replay([{"branchAdd": [todos]}, stage(stage="read")])
        lines = text_of(out["results"][1]).splitlines()
        self.assertIn(f"#1 in_progress build it — pytest -q (exit 1) — {ref} → L5-L8", lines)
        self.assertIn("#2 pending plain — loop anchor", lines)
        self.spec(self.SPEC.replace("## Behavior\n", "## Renamed\n"))
        out = self.replay([{"branchAdd": [todos]}, stage(stage="read")])
        self.assertIn(f"{ref} → missing", text_of(out["results"][1]))

    def test_a_bash_call_that_does_not_match_a_task_anchor_records_nothing(self):
        self.replay([todo_create("t", anchor="pytest -q"), bash_result("ls", 0, "x")])
        self.assertEqual([e["stage"] for e in self.book()[1]], ["kind", "anchor", "task"])

    def test_bare_heading_refs_resolve_against_the_recorded_spec_folder(self):
        self.spec(self.SPEC)
        write = tool_result("write", {"path": self.REF})
        self.replay([todo_create("t"), stage(stage="kind", kind="durable", intent="x"), write,
                     todo_create("u", task_id=2, ref="spec.md#Edge")])
        self.assertEqual(self.tasks()[-1]["refs"], [{"ref": "spec.md#Edge", "range": "L10-L12"}])


class TestSweep(BookCase):
    def write_book(self, path: Path, session: str | None, *entries: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# anchorloop loop book", f'id: "{path.stem}"', f"session: {json.dumps(session)}", "entries:", *[f"- {json.dumps(e)}" for e in entries]]
        path.write_text("\n".join(lines) + "\n")

    def start(self) -> dict:
        return self.replay([{"event": "session_start", "payload": {}}])

    def test_session_start_deletes_dead_books_and_orphaned_children_and_lists_the_rest(self):
        self.replay([todo_create()])
        live = self.book_files()[0]
        mine = live.parent
        gone = "/nonexistent/s.jsonl"
        self.write_book(mine / "dead.yml", gone, {"stage": "kind", "kind": "inline", "intent": "old"}, {"stage": "link", "child": "kid-of-dead"})
        self.write_book(mine / "agents" / "linked.yml", gone)
        self.write_book(mine / "agents" / "orphan.yml", gone)
        self.write_book(mine / "agents" / "kid-of-dead.yml", gone)
        live.write_text(live.read_text() + json.dumps({"stage": "link", "child": "linked"}).join(["- ", "\n"]))
        out = self.start()
        self.assertEqual(sorted(p.name for p in self.books.rglob("*.yml")), sorted([live.name, "linked.yml"]))
        (notice,) = out["notices"]
        self.assertIn("1 open loop book in this project, 3 stale deleted", notice["message"])
        self.assertNotIn("dead.yml", notice["message"])

    def test_session_start_lists_only_the_newest_open_books_and_counts_the_rest(self):
        self.replay([todo_create()])
        mine = self.book_files()[0].parent
        for n in range(5):
            self.write_book(mine / f"b{n}.yml", str(self.session_file), {"stage": "kind", "kind": "inline", "intent": f"intent {n}"})
            os.utime(mine / f"b{n}.yml", (2_000_000_000 + n, 2_000_000_000 + n))
        message = self.start()["notices"][0]["message"]
        lines = message.splitlines()
        self.assertEqual(lines[0], "anchorloop: 6 open loop books in this project")
        self.assertEqual([line.split(": ", 1)[1] for line in lines[1:4]], ["intent 4", "intent 3", "intent 2"])
        self.assertEqual(lines[4], f"  … 3 more in {mine}")
        self.assertEqual(len(lines), 5)

    def test_a_running_child_the_parent_has_not_linked_yet_survives_another_session_start(self):
        # RV-F003: its own session file exists, so it is not stale.
        self.write_book(self.books / "proj" / "agents" / "kid-2.yml", str(self.session_file), {"stage": "kind", "kind": "inline", "intent": "running"})
        self.start()
        self.assertTrue((self.books / "proj" / "agents" / "kid-2.yml").exists())

    def test_an_unlinked_child_without_a_session_goes_after_the_age_limit_only(self):
        fresh = self.books / "proj" / "agents" / "fresh.yml"
        old = self.books / "proj" / "agents" / "old.yml"
        self.write_book(fresh, None)
        self.write_book(old, None)
        os.utime(old, (1, 1))
        self.start()
        self.assertTrue(fresh.exists())
        self.assertFalse(old.exists())

    def test_a_book_older_than_seven_days_goes_even_when_its_session_file_exists(self):
        # RV2-F005
        main = self.books / "proj" / "old-main.yml"
        child = self.books / "proj" / "agents" / "old-kid.yml"
        self.write_book(main, str(self.session_file))
        self.write_book(child, str(self.session_file))
        for path in (main, child):
            os.utime(path, (1, 1))
        self.start()
        self.assertFalse(main.exists() or child.exists())

    def test_only_the_open_books_of_this_project_are_listed(self):
        # RV-F010: a book of another project is neither deleted nor listed.
        self.replay([todo_create()])
        other = self.books / "other-project" / "live.yml"
        self.write_book(other, str(self.session_file), {"stage": "kind", "kind": "reviewed", "intent": "theirs"})
        out = self.start()
        (notice,) = out["notices"]
        self.assertIn("1 open loop book in this project", notice["message"])
        self.assertNotIn("theirs", notice["message"])
        self.assertTrue(other.exists())

    def test_a_quiet_start_with_no_books_says_nothing(self):
        self.assertEqual(self.start()["notices"], [])


class TestParallelAppends(BookCase):
    def test_parallel_writers_keep_the_book_valid_yaml_with_every_entry(self):
        self.replay(self.open_loop())
        steps = [stage(stage="friction", tried="x" * 3000, found="y")] * 15
        procs = [subprocess.Popen(self.command(steps), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env()) for _ in range(6)]
        for proc in procs:
            _, err = proc.communicate()
            self.assertEqual(proc.returncode, 0, err)
        header, entries = self.book()
        self.assertEqual(header["owner"], "main")
        self.assertEqual(len(entries), 2 + 6 * 15)
        self.assertTrue(all(entry["stage"] in ("task", "kind", "friction") for entry in entries))


if __name__ == "__main__":
    unittest.main()
