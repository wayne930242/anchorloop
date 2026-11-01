"""The phase machine over the loop book: sequences per kind, completion from evidence, regression, skip and back, the read phase, reflect."""

import subprocess
import unittest

from tests.pi_harness import assistant, bash_result, stage, todo_create, tool_call, tool_result
from tests.test_pi_book import BookCase, answers, edit, subagent_result, text_of

DIR = "docs/specs/2026-10-29-x"
OPEN_ROWS = "| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which db? | pg | req | grounded |\n| Cache? | | | open |\n"
DONE_ROWS = "| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which db? | pg | req | grounded |\n| Cache? | yes | user | confirmed |\n"
CLOSED_ROWS = "| Question | Answer | Basis | Status |\n|---|---|---|---|\n| Which db? | pg | req | grounded |\n"
DESIGN = "## Approach\n\nUse the existing table.\n"


def spec_text(status: str, approved_from: bool = False) -> str:
    return f"Status: {status}\n{'Approved from: user 2026-10-29' if approved_from else ''}\n\n# Spec\n\n## Behavior\n\nA.\n"


class PhaseCase(BookCase):
    extensions = ("book.ts",)

    def artifact(self, name: str, text: str) -> dict:
        path = self.cwd / DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return tool_result("write", {"path": f"{DIR}/{name}"})

    def line(self, steps: list[dict], **kwargs) -> str:
        return self.read_text(steps, **kwargs).splitlines()[0]


class TestSequences(PhaseCase):
    def test_each_kind_starts_at_its_first_phase(self):
        quick = self.line(self.open_loop("quick"), session="s-quick")
        inline = self.line(self.open_loop("inline"), session="s-inline")
        durable = self.line(self.open_loop("durable"), session="s-durable")
        self.assertEqual(quick, "quick · phase start → act (missing: a change to the code)")
        self.assertTrue(inline.startswith("inline · phase start → anchor (missing: a `Reality anchor:` line"), inline)
        self.assertEqual(durable, "durable · phase start → decide (missing: decision.md with decision rows with Status grounded, confirmed, or open (no spec folder: name it in `intent` by calling `kind` again))")

    def test_an_inline_loop_walks_anchor_act_verify_and_regresses_when_the_code_changes_again(self):
        steps = self.open_loop(anchor="pytest -q")
        self.assertEqual(self.line(steps), "inline · phase anchor ✓ → act (missing: a change to the code)")
        self.assertEqual(self.line([edit()]), "inline · phase act ✓ → verify (missing: a passing run of `pytest -q` after the last change)")
        self.assertEqual(self.line([bash_result("pytest -q", 1, "1 failed")]), "inline · phase act ✓ → fix (missing: the anchor exited 1 after the last change)")
        self.assertIn("→ verify (missing", self.line([edit()]))
        self.assertEqual(self.line([bash_result("pytest -q", 0, "ok")]), "inline · phase verify ✓ → close")
        self.assertIn("phase act ✓ → verify", self.line([edit()]))

    def test_a_reviewed_loop_needs_a_clear_review_after_the_last_change(self):
        self.replay([*self.open_loop("reviewed", anchor="pytest"), edit(), bash_result("pytest", 0, "ok")])
        self.assertIn("phase verify ✓ → review (missing: a review round after the last change", self.line([]))
        self.assertIn("→ fix (missing: blocking review findings are open)", self.line([subagent_result("reviewer", "r1", "Blocking: P0=0 P1=1")]))
        self.replay([edit(), bash_result("pytest", 0, "ok")])
        self.assertIn("→ review (missing: a review round after the last change", self.line([]))
        self.assertEqual(self.line([subagent_result("reviewer", "r2", "Blocking: P0=0 P1=0")]), "reviewed · phase review ✓ → close")

    def test_two_blocking_rounds_in_a_row_ask_for_the_user(self):
        self.replay([*self.open_loop("reviewed", anchor="pytest"), edit(), bash_result("pytest", 0, "ok"), subagent_result("reviewer", "r1", "Blocking: P0=0 P1=2"),
                     edit(), bash_result("pytest", 0, "ok"), subagent_result("reviewer", "r2", "Blocking: P0=0 P1=1")])
        self.assertIn("two consecutive review rounds still blocking: hand the trend to the user", self.line([]))

    def test_a_declared_verify_completes_the_phase_of_a_loop_whose_anchor_is_not_a_command(self):
        stated = {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: the page shows the new column"}]}}}
        self.replay([*self.open_loop(), stated, edit()])
        self.assertEqual(self.line([]), "inline · phase act ✓ → verify (missing: a passing run of `the page shows the new column` after the last change)")
        self.assertEqual(self.line([stage(stage="verify", note="the column is there")]), "inline · phase verify ✓ → close")
        self.assertIn("phase act ✓ → verify", self.line([edit(), bash_result("ls", 0, "x")]))

    def test_the_reality_anchor_line_counts_as_the_anchor_phase_and_a_command_in_it_is_observed(self):
        stated = {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": "Alignment: x\nReality anchor: pytest tests/x.py"}]}}}
        self.replay([*self.open_loop(), stated, edit(), bash_result("pytest tests/x.py", 0, "ok")])
        self.assertEqual(self.entries("anchor")[0]["line"], True)
        self.assertEqual([e["exit"] for e in self.entries("verify")], [0])
        self.assertEqual(self.line([]), "inline · phase verify ✓ → close")

    def test_a_bare_reality_anchor_line_still_counts(self):
        stated = {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor:\n- pytest"}]}}}
        self.replay([*self.open_loop(), stated])
        self.assertEqual(self.line([]), "inline · phase anchor ✓ → act (missing: a change to the code)")

    def test_a_reality_anchor_line_stated_before_the_loop_opened_counts_once_it_opens(self):
        branch = [{"type": "message", "message": {"role": "user", "content": "fix"}},
                  {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest"}]}}]
        self.replay([todo_create(), stage(stage="kind", kind="inline", intent="x")], branch=branch)
        self.assertEqual(self.entries("anchor")[0]["check"], "pytest")


class TestDurable(PhaseCase):
    def test_a_durable_loop_walks_decide_grill_spec_read_approve_design_anchor(self):
        self.replay(self.open_loop("durable"))
        self.assertIn("phase decide ✓ → grill (missing: 1 open decision row)", self.line([self.artifact("decision.md", OPEN_ROWS)]))
        self.assertIn("phase grill ✓ → spec (missing: spec.md with Status: proposed)", self.line([self.artifact("decision.md", DONE_ROWS)]))
        self.assertIn("phase spec ✓ → read (missing: a fresh-context read of the spec", self.line([self.artifact("spec.md", spec_text("proposed"))]))
        self.assertIn("phase read ✓ → approve (missing: spec.md Status: approved with Approved from (now proposed))", self.line([stage(stage="fresh-read", note="a new session")]))
        self.assertIn("phase approve ✓ → design (missing: design.md with its approach section filled)", self.line([self.artifact("spec.md", spec_text("approved", True))]))
        self.assertIn("phase design ✓ → anchor (missing:", self.line([self.artifact("design.md", DESIGN)]))
        self.assertEqual(self.line([stage(stage="kind", anchor="pytest -q")]), "durable · phase anchor ✓ → act (missing: a change to the code)")

    def test_a_spec_edited_back_to_proposed_regresses_approve_and_what_follows(self):
        self.replay([*self.open_loop("durable", anchor="pytest -q"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed")),
                     stage(stage="fresh-read"), self.artifact("design.md", DESIGN)])
        self.replay([self.artifact("spec.md", spec_text("approved", True))])
        self.assertTrue(self.line([]).startswith("durable · phase anchor ✓ → act (missing: a change to the code)"))
        self.assertIn("phase read ✓ → approve (missing: spec.md Status: approved with Approved from (now proposed))", self.line([self.artifact("spec.md", spec_text("proposed"))]))

    def test_amending_an_approved_spec_that_stays_approved_keeps_read(self):
        # RV2-F003
        for name, text in (("decision.md", DONE_ROWS), ("spec.md", spec_text("approved", True)), ("design.md", DESIGN)):
            self.artifact(name, text)
        self.replay(self.open_loop("durable", intent=f"implement {DIR}", anchor="pytest -q"))
        line = self.line([self.artifact("spec.md", spec_text("approved", True) + "\nAmendment 1.\n")])
        self.assertEqual(line, "durable · phase anchor ✓ → act (missing: a change to the code)")

    def test_a_spec_that_names_no_approval_is_not_approved(self):
        self.replay([*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed")), stage(stage="fresh-read")])
        self.assertIn("→ approve (missing: spec.md Status: approved with Approved from (now approved))", self.line([self.artifact("spec.md", spec_text("approved", False))]))

    def test_grill_is_skipped_by_itself_when_the_decision_table_never_had_an_open_row(self):
        text = self.line([*self.open_loop("durable"), self.artifact("decision.md", CLOSED_ROWS)])
        self.assertIn("phase decide ✓ → spec", text)
        self.assertIn("skipped: grill (no open rows)", text)

    def test_a_design_with_an_empty_approach_is_not_designed(self):
        self.replay([*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("approved", True)), stage(stage="fresh-read")])
        self.assertIn("→ design (missing:", self.line([self.artifact("design.md", "## Approach\n\n## Risks\n\nY.\n")]))

    def test_a_pickup_loop_finds_the_spec_through_its_intent_and_reads_artifacts_from_disk(self):
        for name, text in (("decision.md", DONE_ROWS), ("spec.md", spec_text("approved", True)), ("design.md", DESIGN)):
            self.artifact(name, text)
        line = self.line(self.open_loop("durable", intent=f"implement {DIR}", anchor="pytest -q"))
        self.assertEqual(line, "durable · phase anchor ✓ → act (missing: a change to the code)")

    def test_a_pickup_loop_names_the_spec_in_a_todo_ref(self):
        for name, text in (("decision.md", DONE_ROWS), ("spec.md", spec_text("approved", True))):
            self.artifact(name, text)
        steps = [todo_create("build", ref=f"{DIR}/spec.md#Behavior"), stage(stage="kind", kind="durable", intent="build it")]
        self.assertIn("phase approve ✓ → design", self.line(steps))


class TestRead(PhaseCase):
    BRIEF = f"You have no context. Read {DIR}/spec.md, restate the contract, and list what you had to guess."

    def proposed(self) -> list[dict]:
        return [*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed"))]

    def goldfish(self) -> list[dict]:
        return self.entries("goldfish")

    def test_a_returned_subagent_whose_brief_names_the_spec_is_judged_by_jev_as_a_fresh_read(self):
        self.replay(self.proposed())
        out = self.replay([subagent_result("scout", "fresh", "Contract: A. Guessed: none.", self.BRIEF)], classify=answers(fresh_read=0.9))
        (entry,) = self.goldfish()
        self.assertEqual((entry["source"], entry["ok"], entry["child"]), ("jev", True, "fresh"))
        self.assertEqual(out["classifyCalls"][0]["brief"], self.BRIEF)
        self.assertIn("phase read ✓ → approve", self.line([]))

    def test_the_spec_path_is_only_a_pre_filter(self):
        self.replay(self.proposed())
        out = self.replay([subagent_result("scout", "other", "done", "Look at src/app.py"), subagent_result("scout", "again", "done", "Look at docs")], classify=answers(fresh_read=0.9))
        self.assertEqual((self.goldfish(), out["classifyCalls"]), ([], []))
        self.replay([subagent_result("worker", "fixer", "I fixed it", self.BRIEF)], classify=answers(fresh_read=0.1))
        (entry,) = self.goldfish()
        self.assertFalse(entry["ok"])
        self.assertIn("phase spec ✓ → read", self.line([]))

    def test_without_a_jev_key_the_read_stays_missing_for_the_manual_declaration(self):
        self.replay(self.proposed())
        self.replay([subagent_result("scout", "fresh", "ok", self.BRIEF)], classify="no-auth")
        self.assertEqual(self.goldfish(), [])
        self.replay([stage(stage="fresh-read", note="read by hand")])
        self.assertEqual((self.goldfish()[0]["source"], self.goldfish()[0]["note"]), ("declared", "read by hand"))
        self.assertIn("phase read ✓ → approve", self.line([]))

    def test_a_manual_declaration_skips_detection(self):
        self.replay([*self.proposed(), stage(stage="fresh-read")])
        out = self.replay([subagent_result("scout", "fresh", "ok", self.BRIEF)], classify=answers(fresh_read=0.9))
        self.assertEqual(out["classifyCalls"], [])
        self.assertEqual(len(self.goldfish()), 1)

    def test_no_detection_happens_before_the_spec_is_proposed(self):
        self.replay([*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("draft"))])
        out = self.replay([subagent_result("scout", "early", "ok", self.BRIEF)], classify=answers(fresh_read=0.9))
        self.assertEqual(out["classifyCalls"], [])


class TestSkipAndBack(PhaseCase):
    def test_skip_names_a_phase_of_the_kind_and_the_reason_shows_in_the_phase_line(self):
        out = self.replay([*self.open_loop(), stage(stage="skip", phase="decide", reason="x"), stage(stage="skip", phase="close", reason="x"), stage(stage="skip", phase="anchor"),
                           stage(stage="skip", phase="anchor", reason="a typo")])
        self.assertIn("one of anchor, act, verify, reflect", out["results"][2]["error"])
        self.assertIn("phase", out["results"][3]["error"])
        self.assertIn("reason", out["results"][4]["error"])
        self.assertEqual(self.line([]), "inline · phase start → act (missing: a change to the code) · skipped: anchor (a typo)")

    def test_a_skipped_phase_counts_for_the_ones_after_it(self):
        self.replay([*self.open_loop(), stage(stage="skip", phase="anchor", reason="no check exists")])
        self.assertEqual(self.line([edit(), stage(stage="skip", phase="verify", reason="docs only")]), "inline · phase act ✓ → close · skipped: anchor (no check exists), verify (docs only)")

    def test_back_makes_a_phase_and_those_after_it_count_only_on_new_evidence(self):
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.line([]), "inline · phase verify ✓ → close")
        self.assertEqual(self.line([stage(stage="back", phase="act", reason="the first try was wrong")]),
                         "inline · phase anchor ✓ → act (missing: a change to the code) · back: act (the first try was wrong)")
        self.assertIn("phase act ✓ → verify", self.line([edit()]))
        self.assertEqual(self.line([bash_result("pytest -q", 0, "ok")]).split(" · back")[0], "inline · phase verify ✓ → close")

    def test_back_to_an_artifact_phase_needs_a_new_write(self):
        self.replay([*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed"))])
        self.assertIn("phase decide ✓ → spec", self.line([stage(stage="back", phase="spec", reason="rewrite the contract")]))
        self.assertIn("phase spec ✓ → read", self.line([self.artifact("spec.md", spec_text("proposed"))]))

    def test_back_validates_its_phase_and_reason(self):
        out = self.replay([*self.open_loop(), stage(stage="back", phase="review", reason="x"), stage(stage="back", phase="act")])
        self.assertIn("one of", out["results"][2]["error"])
        self.assertIn("reason", out["results"][3]["error"])

    def test_the_close_summary_and_session_entry_show_skips_and_backs(self):
        out = self.replay([*self.open_loop(), stage(stage="skip", phase="anchor", reason="no check"), edit(), stage(stage="back", phase="act", reason="redo"), edit(),
                           stage(stage="skip", phase="verify", reason="docs"), stage(stage="close", verdict="landed")])
        self.assertEqual(text_of(out["results"][-1]), "closed (landed). Clear the todo list.")
        data = out["appended"][0]["data"]
        self.assertEqual((data["skipped"], data["back"]), (["anchor (no check)", "verify (docs)"], ["act (redo)"]))


class TestCloseAndReflect(PhaseCase):
    def test_closing_with_incomplete_phases_warns_in_one_line_and_never_refuses(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="close", verdict="landed")])
        self.assertEqual(text_of(out["results"][-1]),
                         "closed (landed). not complete: act (a change to the code); verify (a passing run of `pytest -q` after the last change). Clear the todo list.")

    def test_closing_as_abandoned_or_blocked_is_not_a_jump(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), stage(stage="close", verdict="abandoned")])
        self.assertNotIn("anchorloop:", text_of(out["results"][-1]))

    def test_a_quick_loop_gets_one_reminder_at_close_and_nothing_before(self):
        out = self.replay([*self.open_loop("quick", anchor="make lint"), edit(), stage(stage="close", verdict="landed")])
        self.assertTrue(text_of(out["results"][-1]).startswith("closed (landed). not complete: check ("), text_of(out["results"][-1]))

    def test_reflect_is_the_last_phase_before_close_and_completes_when_every_friction_has_a_reflect(self):
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.line([]), "inline · phase verify ✓ → close")
        self.assertIn("phase verify ✓ → reflect (missing: 1 friction entry without a reflect)", self.line([stage(stage="friction", tried="a", found="b")]))
        self.assertEqual(self.line([stage(stage="reflect", friction=[1], **{"class": "gap"})]), "inline · phase reflect ✓ → close")

    def test_closing_with_unreflected_friction_is_a_jump_that_warns_and_lists_it(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok"), stage(stage="friction", tried="a", found="b"), stage(stage="close", verdict="landed")])
        text = text_of(out["results"][-1])
        self.assertEqual(text, "closed (landed). not complete: reflect (1 friction entry without a reflect). unreflected friction: 1 (b). Clear the todo list.")

    def test_reflect_can_be_skipped(self):
        self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok"), stage(stage="friction", tried="a", found="b")])
        self.assertIn("skipped: reflect (resolved in the change)", self.line([stage(stage="skip", phase="reflect", reason="resolved in the change")]))



class TestReclassify(PhaseCase):
    def wide(self) -> list[dict]:
        """Three source files in two modules, the reach that asks an unreviewed loop to re-classify."""
        return [{"file": "src/a.py", "text": "a\n"}, {"file": "src/b.py", "text": "b\n"}, {"file": "lib/c.py", "text": "c\n"}, edit("src/a.py")]

    def test_changing_the_kind_needs_a_reason(self):
        out = self.replay([*self.open_loop("inline"), stage(stage="kind", kind="reviewed"), stage(stage="kind", kind="reviewed", reason="the reader moved to 9 callers")])
        self.assertIn("needs `reason`", out["results"][2]["error"])
        self.assertEqual(text_of(out["results"][3]), "ok")
        self.assertEqual(self.entries("kind")[-1]["reason"], "the reader moved to 9 callers")

    def test_a_reason_lets_the_kind_drop(self):
        out = self.replay([*self.open_loop("reviewed", anchor="pytest"), edit(), bash_result("pytest", 0, "ok"), subagent_result("reviewer", "r1", "Blocking: P0=0 P1=0"),
                           stage(stage="kind", kind="inline", reason="one file after all")])
        self.assertEqual(text_of(out["results"][-1]), "ok")
        self.assertEqual(self.entries("kind")[-1]["kind"], "inline")

    def test_an_anchor_run_past_the_reach_asks_an_inline_loop_to_reclassify_until_kind_answers(self):
        self.git_repo()
        out = self.replay([*self.open_loop(anchor="pytest -q"), *self.wide(), bash_result("pytest -q", 0, "ok")])
        notice = text_of(out["results"][-1]).splitlines()[-1]
        self.assertEqual(notice, "anchorloop: reach 3 files / 2 modules (lib, src); kind with reason: reviewed, or why inline fits.")
        self.assertIn("→ verify (missing: reach 3 files / 2 modules (lib, src)", self.line([]))
        self.assertEqual(self.line([stage(stage="kind", kind="inline", reason="three one-line renames")]), "inline · phase verify ✓ → close")
        self.assertEqual(self.entries("kind")[-1]["crossed"], ["files", "modules"])

    def test_a_todo_only_loop_measures_bash_made_changes_and_sees_a_commit_as_act(self):
        self.git_repo()
        out = self.replay([todo_create(), assistant("Reality anchor: pytest -q"), {"file": "src/a.py", "text": "a\n"}, {"file": "src/b.py", "text": "b\n"}, {"file": "lib/c.py", "text": "c\n"}, bash_result("pytest -q", 0, "ok")])
        self.assertIn("anchorloop: reach 3 files / 2 modules (lib, src)", text_of(out["results"][-1]))
        self.assertEqual(len(self.entries("base")), 1)

    def test_a_todo_only_loop_sees_a_commit_as_act(self):
        self.git_repo()
        (self.cwd / "app.py").write_text("print(2)\n")
        self.replay([todo_create(), assistant("Reality anchor: pytest -q")])
        subprocess.run(["git", "-C", str(self.cwd), "commit", "-qam", "wip"], check=True, capture_output=True)
        self.replay([bash_result("git commit -am wip", 0, "[main abc] wip")])
        self.assertEqual(self.entries("edit")[0]["via"], "commit")

    def test_upgrading_answers_the_reach_and_a_reviewed_loop_is_never_asked(self):
        self.git_repo()
        out = self.replay([*self.open_loop("reviewed", anchor="pytest -q"), *self.wide(), bash_result("pytest -q", 0, "ok")])
        self.assertIsNone(out["results"][-1])
        self.assertIn("phase verify ✓ → review", self.line([]))

    def test_a_criterion_the_answer_did_not_cover_asks_again(self):
        self.git_repo()
        self.replay([*self.open_loop(anchor="pytest -q"), *self.wide(), bash_result("pytest -q", 0, "ok"), stage(stage="kind", kind="inline", reason="renames")])
        out = self.replay([{"file": "README.md", "text": "a new flag\n"}, bash_result("pytest -q", 0, "ok")])
        self.assertIn("/ README.md;", text_of(out["results"][-1]))
        self.assertIn("→ verify (missing: reach", self.line([]))

    def test_a_quick_loop_is_asked_at_its_check(self):
        self.git_repo()
        self.replay([*self.open_loop("quick", anchor="make lint"), *self.wide(), bash_result("make lint", 0, "ok")])
        self.assertIn("quick · phase act ✓ → check (missing: reach 3 files", self.line([]))

    def test_a_declared_verify_measures_the_reach_too(self):
        self.git_repo()
        out = self.replay([*self.open_loop(anchor="the page shows the column"), *self.wide(), stage(stage="verify", note="the column is there")])
        self.assertIn("anchorloop: reach 3 files", text_of(out["results"][-1]))
        self.assertIn("→ verify (missing: reach 3 files", self.line([]))

    def test_tests_lockfiles_specs_and_a_readme_without_source_do_not_count(self):
        self.git_repo()
        files = [{"file": f, "text": "x\n"} for f in ("src/a.py", "tests/test_a.py", "src/a.test.ts", "pkg/b_test.go", "uv.lock", f"{DIR}/spec.md")]
        self.replay([*self.open_loop(anchor="pytest -q"), *files, edit("src/a.py"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.entries("verify")[-1]["reach"], {"source": ["src/a.py"], "modules": ["src"], "behavior": [], "crossed": []})
        self.assertEqual(self.line([]), "inline · phase verify ✓ → close")
        (self.cwd / "src/a.py").unlink()
        self.replay([{"file": "README.md", "text": "x\n"}, bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.entries("verify")[-1]["reach"]["crossed"], [])


class TestReachEdges(PhaseCase):
    """Review round 1 (R-F001..R-F007): what the reach counts and how its line reads."""

    def reach(self) -> dict:
        return self.entries("verify")[-1]["reach"]

    def test_files_dirty_before_the_loop_count_only_once_the_loop_changes_them(self):
        self.git_repo()
        (self.cwd / "app.py").write_text("print(2)\n")
        for name in ("notes", ".cache/conf", "lib/old.py"):
            (self.cwd / name).parent.mkdir(parents=True, exist_ok=True)
            (self.cwd / name).write_text("before\n")
        self.replay([*self.open_loop(anchor="pytest -q"), {"file": "src/a.py", "text": "a\n"}, edit("src/a.py"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.reach()["source"], ["src/a.py"])
        self.replay([{"file": "lib/old.py", "text": "changed in the loop\n"}, bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.reach()["source"], ["lib/old.py", "src/a.py"])

    def test_a_path_git_cannot_hash_hides_no_other_pre_dirty_file(self):
        self.git_repo()
        (self.cwd / "lib").mkdir()
        (self.cwd / "lib/old.py").write_text("before\n")
        (self.cwd / "lib/keep.py").write_text("before\n")
        subprocess.run(["git", "-C", str(self.cwd), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.cwd), "commit", "-qm", "lib"], check=True, capture_output=True)
        (self.cwd / "lib/old.py").write_text("dirty before the loop\n")
        (self.cwd / "lib/keep.py").write_text("dirty before the loop, never touched\n")
        (self.cwd / "app.py").unlink()
        (self.cwd / "app.py").mkdir()
        (self.cwd / "app.py/inner.txt").write_text("x\n")
        self.replay([*self.open_loop(anchor="pytest -q"), {"file": "lib/old.py", "text": "changed in the loop\n"}, bash_result("pytest -q", 0, "ok")])
        # Each other path still hashes alone, and the one git cannot hash counts, since its hash proves nothing.
        self.assertEqual(self.reach()["source"], ["app.py", "lib/old.py"])

    def test_a_repo_first_reached_by_a_merge_counts_the_merged_files_but_not_its_older_work(self):
        other = self.cwd / "merged"
        other.mkdir()
        git = lambda *args: subprocess.run(["git", "-C", str(other), *args], check=True, capture_output=True)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            git(*args)
        (other / "base.txt").write_text("b\n")
        git("add", ".")
        git("commit", "-qm", "base")
        git("switch", "-qc", "feature")
        for name in ("src/a.py", "src/b.py", "lib/c.py"):
            (other / name).parent.mkdir(parents=True, exist_ok=True)
            (other / name).write_text("x\n")
        git("add", ".")
        git("commit", "-qm", "feature")
        git("switch", "-q", "main")
        (other / "wip").mkdir()
        (other / "wip/x.py").write_text("older work\n")
        git("merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        self.replay([*self.open_loop(anchor="pytest -q"), bash_result(f"git -C {other} merge feature", 0, "Merge made"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.reach()["source"], ["lib/c.py", "src/a.py", "src/b.py"])

    def test_a_second_repo_keeps_each_repos_directories_as_modules(self):
        self.git_repo()
        other = self.cwd / "vendor-repo"
        other.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(other), *args], check=True, capture_output=True)
        (other / "x.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(other), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "base"], check=True, capture_output=True)
        (self.cwd / ".gitignore").write_text("vendor-repo/\n")
        steps = [*self.open_loop(anchor="pytest -q"), {"file": "src/a.py", "text": "a\n"}, {"file": "lib/b.py", "text": "b\n"}, edit("src/a.py"),
                 tool_call("edit", str(other / "x.txt")), {"file": "vendor-repo/x.txt", "text": "y\n"}, edit(str(other / "x.txt")), bash_result("pytest -q", 0, "ok")]
        self.replay(steps)
        self.assertEqual(len(self.entries("base")), 2)
        self.assertEqual(self.reach()["crossed"], ["modules"])
        self.assertEqual(len(self.reach()["modules"]), 2)

    def test_scratch_and_spec_readmes_and_source_named_readme_are_not_behavior_files(self):
        self.git_repo()
        files = [{"file": f, "text": "x\n"} for f in ("src/readme_render.py", "scratch/README.md", f"{DIR}/README.md")]
        self.replay([*self.open_loop(anchor="pytest -q"), *files, edit("src/readme_render.py"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual((self.reach()["source"], self.reach()["behavior"]), (["src/readme_render.py"], []))

    def test_root_files_count_as_files_but_not_as_a_module_and_more_lockfiles_and_fixtures_are_skipped(self):
        self.git_repo()
        files = [{"file": f, "text": "x\n"} for f in ("package.json", "pi/book.ts", "flake.lock", "tests/fixtures/a.json", "testdata/b.json", "conftest.py")]
        self.replay([*self.open_loop(anchor="pytest -q"), *files, edit("pi/book.ts"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(self.reach(), {"source": ["package.json", "pi/book.ts"], "modules": ["pi"], "behavior": [], "crossed": []})

    def test_the_line_keeps_the_bash_structured_content(self):
        self.git_repo()
        out = self.replay([*self.open_loop(anchor="pytest -q"), {"file": "src/a.py", "text": "a\n"}, {"file": "src/b.py", "text": "b\n"}, {"file": "lib/c.py", "text": "c\n"},
                           edit("src/a.py"), bash_result("pytest -q", 0, "ok")])
        self.assertEqual(out["results"][-1].get("structuredContent"), {"exit_code": 0, "output": "ok"})

    def test_a_loop_a_todo_create_opened_is_asked_like_any_inline_loop(self):
        self.git_repo()
        stated = {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": "Reality anchor: pytest -q"}]}}}
        out = self.replay([todo_create(), stated, tool_call("write", "src/a.py"), {"file": "src/a.py", "text": "a\n"}, {"file": "src/b.py", "text": "b\n"}, {"file": "lib/c.py", "text": "c\n"},
                           edit("src/a.py"), bash_result("pytest -q", 0, "ok")])
        self.assertIn("kind with reason: reviewed, or why inline fits", text_of(out["results"][-1]))

if __name__ == "__main__":
    unittest.main()
