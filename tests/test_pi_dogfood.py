"""Regressions found by dogfooding the loop book: act evidence outside the cwd, chained anchors, close output, fresh-read judging."""

import subprocess
import unittest
from pathlib import Path

from tests.pi_harness import bash_result, stage, todo_create, todo_state, tool_call, tool_result
from tests.test_pi_anchorloop import TestAnchorGate, touch
from tests.test_pi_anchorloop import answers as jev_answers
from tests.test_pi_book import BookCase, answers, edit, subagent_result, text_of
from tests.test_pi_phases import DIR, DONE_ROWS, PhaseCase, spec_text


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    (path / "lib.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "base"], check=True, capture_output=True)


class TestActEvidence(BookCase):
    def test_a_write_in_a_git_repo_outside_the_cwd_counts_even_under_a_temp_dir(self):
        other = self.cwd.parent / "other"
        init_repo(other)
        self.replay([*self.open_loop(), edit(str(other / "lib.py"))])
        self.assertEqual(self.stages(), ["kind", "edit"])

    def test_scratch_and_spec_folders_of_that_repo_and_non_repo_temp_files_stay_artifacts(self):
        other = self.cwd.parent / "other"
        init_repo(other)
        loose = self.cwd.parent / "loose"
        loose.mkdir()
        self.replay([*self.open_loop(), edit(str(other / "scratch" / "x.py")), edit(str(other / "docs" / "specs" / "d" / "notes.py")), edit(str(loose / "x.py"))])
        self.assertEqual(self.entries("edit"), [])

    def test_the_gate_uses_the_same_rule(self):
        other = self.cwd.parent / "other"
        init_repo(other)
        loose = self.cwd.parent / "loose"
        loose.mkdir()
        gate = TestAnchorGate()
        out = self.replay([*gate.loop(), *touch("edit", str(other / "scratch" / "x.py"), "c1"), *touch("edit", str(loose / "x.py"), "c2"), *touch("edit", str(other / "lib.py"), "c3")], extensions=("book.ts", "anchor-gate.ts"))
        self.assertEqual(out["notices"], [])
        self.assertEqual([step for step, _ in gate.lines(out)], [len(out["results"]) - 2])

    def test_read_only_git_commands_and_no_op_pulls_are_not_act(self):
        self.replay([
            *self.open_loop(anchor="pytest"),
            bash_result("git merge-base HEAD origin/master", 0, "abc"),
            bash_result("git merge --abort", 0, ""),
            bash_result("git config pull.rebase false", 0, ""),
            bash_result("git log -- pi/pull.ts", 0, ""),
            bash_result("git pull", 0, "Already up to date."),
        ])
        self.assertEqual(self.entries("edit"), [])
        self.replay([bash_result("git -C /tmp/x pull --ff-only", 0, "Fast-forward")])
        self.assertEqual([e["via"] for e in self.entries("edit")], ["merge"])

    def test_a_successful_git_merge_cherry_pick_or_pull_counts_as_act_and_a_failed_one_does_not(self):
        self.replay([*self.open_loop(anchor="pytest"), bash_result("git merge feature", 1, "conflict")])
        self.assertEqual(self.entries("edit"), [])
        self.replay([bash_result("git merge feature", 0, "Merge made"), bash_result("git cherry-pick abc", 0, "ok")])
        self.assertEqual([e["via"] for e in self.entries("edit")], ["merge"])
        self.replay([bash_result("pytest", 0, "ok"), bash_result("git pull --ff-only", 0, "ok")])
        self.assertEqual(len(self.entries("edit")), 2)


class TestReview4(BookCase):
    def exits(self, command: str, code: int, anchor: str = "pytest -q") -> list:
        self.replay([*self.open_loop(anchor=anchor), bash_result(command, code, "out")])
        return [e["exit"] for e in self.entries("verify")]

    def test_the_anchor_named_again_in_text_after_its_run_does_not_hide_the_separator(self):
        self.assertEqual(self.exits('pytest -q || echo "pytest -q failed"', 0)[-1], "unknown")
        self.assertEqual(self.exits("pytest -q; echo done pytest -q", 0)[-1], "unknown")

    def test_a_longer_word_is_not_a_run_of_a_short_anchor(self):
        self.assertEqual(self.exits("cmake ..", 0, anchor="make"), [])
        self.assertEqual(self.exits("make test; cmake ..", 0, anchor="make test")[-1], "unknown")

    def test_only_the_tail_of_a_two_check_anchor_is_not_a_run_of_the_anchor(self):
        self.assertEqual(self.exits("node --test", 0, anchor="pytest -q && node --test"), [])
        self.assertEqual(self.exits("pytest -q && node --test", 0, anchor="pytest -q && node --test"), [0])

    def test_pipefail_in_quotes_or_turned_off_again_does_not_count(self):
        self.assertEqual(self.exits('echo "set -o pipefail"; pytest -q | tail -3', 0)[-1], "unknown")
        self.assertEqual(self.exits("set -o pipefail; set +o pipefail; pytest -q | tail -3", 0)[-1], "unknown")
        self.assertEqual(self.exits("cd x && set -o pipefail; pytest -q 2>&1 | tail -3", 1)[-1], 1)

    def test_a_cd_or_export_prefix_is_part_of_the_check(self):
        self.assertEqual(self.exits("cd other && npm test", 0, anchor="cd app && npm test"), [])
        self.assertEqual(self.exits(". .venv/bin/activate && pytest -q", 1, anchor=". .venv/bin/activate && pytest -q"), [1])

    def test_substitutions_guarded_subshells_and_comments_are_not_runs_with_a_trustworthy_exit(self):
        for command in ("echo $(pytest -q)", "diff <(pytest -q) exp", "true || (pytest -q)", "[ -d .venv ] || (cd x && pytest -q)", "! (pytest -q)", "(set -o pipefail); pytest -q | tail", "echo hi #; pytest -q"):
            with self.subTest(command=command):
                self.assertIn(self.exits(command, 0)[-1:], ([], ["unknown"]))

    def test_a_comment_with_an_apostrophe_does_not_hide_a_later_separator(self):
        self.assertEqual(self.exits("pytest -q  # don't touch\necho 'x' || true", 0)[-1], "unknown")
        self.assertEqual(self.exits("timeout || pytest -q", 0)[-1], "unknown")

    def test_common_wrappers_still_count_as_a_run(self):
        for command in ("uv run pytest -q", "time pytest -q", "timeout 600 pytest -q", "env A=1 pytest -q", "(cd x && pytest -q)"):
            with self.subTest(command=command):
                self.assertEqual(self.exits(command, 1)[-1], 1)

    def test_a_multi_commit_cherry_pick_bases_on_the_head_before_the_first_pick(self):
        repo = self.cwd.parent / "multi"
        repo.mkdir()
        run = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        (repo / "a.py").write_text("a")
        run("add", "a.py")
        run("commit", "-qm", "a")
        run("checkout", "-qb", "side")
        picks = []
        for name in ("c", "d", "e"):
            (repo / f"{name}.py").write_text(name)
            run("add", f"{name}.py")
            run("commit", "-qm", name)
            picks.append(run("rev-parse", "HEAD"))
        run("checkout", "-q", "-")
        before = run("rev-parse", "HEAD")
        run("cherry-pick", *picks)
        self.replay([*self.open_loop(anchor="pytest"), bash_result(f"cd {repo} && git cherry-pick {' '.join(picks)}", 0, "ok")])
        self.assertEqual([e["head"] for e in self.entries("base") if e["repo"] == str(repo.resolve())], [before])

    def test_a_cherry_pick_first_seen_through_bash_bases_on_the_head_before_it_not_a_stale_orig_head(self):
        repo = self.cwd.parent / "other"
        repo.mkdir()
        run = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        for name in ("a", "b", "c"):
            (repo / f"{name}.py").write_text(name)
            run("add", f"{name}.py")
            run("commit", "-qm", name)
        run("update-ref", "ORIG_HEAD", "HEAD~2")
        run("checkout", "-qb", "side")
        (repo / "d.py").write_text("d")
        run("add", "d.py")
        run("commit", "-qm", "d")
        pick = run("rev-parse", "HEAD")
        run("checkout", "-q", "-")
        before = run("rev-parse", "HEAD")
        run("cherry-pick", pick)
        self.replay([*self.open_loop(anchor="pytest"), bash_result(f"git -C {repo} cherry-pick {pick}", 0, "1 file changed")])
        self.assertEqual([e["head"] for e in self.entries("base") if e["repo"] == str(repo.resolve())], [before])


class TestChildAct(BookCase):
    ENV = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "worker-1"}

    def test_a_linked_childs_edits_count_as_the_coordinators_act(self):
        env = {**self.ENV, "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay([*self.open_loop("inline", "child work"), edit()], env=env)
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "worker-1", "agent": "worker", "status": "started"})
        text = self.read_text([*self.open_loop(anchor="pytest -q"), link])
        self.assertEqual(text.splitlines()[0], "inline · phase act ✓ → verify (missing: a passing run of `pytest -q` after the last change)")
        out = self.replay([bash_result("pytest -q", 0, "ok"), stage(stage="read")])
        self.assertEqual(text_of(out["results"][-1]).splitlines()[0], "inline · phase verify ✓ → close")

    def test_a_childs_edit_after_main_verified_makes_the_verify_stale(self):
        env = {**self.ENV, "PI_SUBAGENT_SESSION": str(self.session_file)}
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "worker-1", "agent": "worker", "status": "started"})
        self.replay([*self.open_loop(anchor="pytest -q"), link, bash_result("pytest -q", 0, "ok")])
        self.replay([*self.open_loop("inline", "child work"), edit()], env=env)
        text = self.read_text([])
        self.assertIn("phase act ✓ → verify", text.splitlines()[0])
        self.assertIn("(before the last change)", text)


class TestAnchorChains(BookCase):
    def exits(self, command: str, code: int) -> list:
        self.replay([*self.open_loop(anchor="pytest -q"), bash_result(command, code, "out")])
        return [e["exit"] for e in self.entries("verify")]

    def test_an_and_chain_that_exits_zero_ran_the_anchor_to_success_even_with_a_pipe_after_it(self):
        self.assertEqual(self.exits("pytest -q && echo done | tee log", 0), [0])

    def test_a_pipe_directly_after_the_anchor_is_unknown_unless_pipefail_is_set(self):
        self.assertEqual(self.exits("pytest -q 2>&1 | tail -3", 0), ["unknown"])

    def test_pipefail_makes_the_exit_code_trustworthy(self):
        self.assertEqual(self.exits("set -o pipefail; pytest -q 2>&1 | tail -3", 1), [1])

    def test_pipefail_counts_anywhere_before_the_anchor(self):
        self.assertEqual(self.exits("cd /tmp && . .venv/bin/activate && set -o pipefail; pytest -q 2>&1 | tail -3", 1)[-1], 1)
        self.assertEqual(self.exits("set -euo pipefail; pytest -q 2>&1 | tail -3", 0)[-1], 0)
        self.assertEqual(self.exits("set -o errexit -o pipefail; pytest -q 2>&1 | tail -3", 1)[-1], 1)

    def test_the_last_occurrence_of_the_anchor_decides(self):
        self.assertEqual(self.exits("pytest -q; cd main && git merge --ff-only && pytest -q", 1), [1])

    def test_an_anchor_with_an_environment_prefix_matches_on_its_last_segment(self):
        self.replay([*self.open_loop(anchor=". /tmp/x/.venv/bin/activate && pytest -q"), bash_result("pytest -q", 1, "bad")])
        self.assertEqual([e["exit"] for e in self.entries("verify")], [1])

    def test_or_semicolon_and_later_pipes_after_or_hide_the_anchor_exit(self):
        self.assertEqual(self.exits("pytest -q || true", 0)[-1], "unknown")
        self.assertEqual(self.exits("set -o pipefail; pytest -q || true", 0)[-1], "unknown")
        self.assertEqual(self.exits("set -o pipefail; pytest -q | tail; true", 0)[-1], "unknown")
        self.assertEqual(self.exits("pytest -q && git commit -m x", 1)[-1], 1)
        self.assertEqual(self.exits("! pytest -q", 0)[-1], "unknown")
        self.assertEqual(self.exits("true || pytest -q", 0)[-1], "unknown")
        self.assertEqual(self.exits("pytest -q & wait", 0)[-1], "unknown")


class TestCloseOutput(BookCase):
    def test_close_lists_phases_from_the_phase_machine_and_only_repos_with_tracked_changes(self):
        self.git_repo()
        other = self.cwd.parent / "other"
        init_repo(other)
        (other / "new.py").write_text("untracked\n")
        steps = [*self.open_loop(anchor="pytest -q"), tool_call("edit", str(other / "lib.py")), tool_call("edit", "app.py"), edit(), bash_result("pytest -q", 0, "ok"),
                 stage(stage="skip", phase="reflect", reason="nothing to reflect")]
        # The change is on disk before the anchor runs: a change after the run is no longer covered by it (issue #7).
        (self.cwd / "app.py").write_text("print(1)\nprint(2)\n")
        self.replay(steps)
        out = self.replay([stage(stage="close", verdict="landed")])
        self.assertEqual(text_of(out["results"][-1]), "closed (landed). Clear the todo list.")
        diff = out["appended"][0]["data"]["diff"]
        self.assertIn("work: 1 file changed", diff)
        self.assertNotIn("other:", diff)
        self.assertNotIn("untracked", diff)

    def test_automatic_skips_are_marked_and_the_phase_list_goes_into_the_session_entry(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok"), stage(stage="close", verdict="landed")])
        self.assertEqual(text_of(out["results"][-1]), "closed (landed). Clear the todo list.")
        phases = out["appended"][0]["data"]["phases"]
        self.assertEqual(phases[-1], {"phase": "reflect", "state": "auto-skipped", "note": "no friction"})

    def test_no_notice_when_nothing_is_missing(self):
        out = self.replay([*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok"), stage(stage="close", verdict="landed")])
        self.assertNotIn("anchorloop:", text_of(out["results"][-1]))

    def test_close_leaves_no_empty_project_or_agents_directory(self):
        env = {"PI_SUBAGENT_ID": "kid", "PI_SUBAGENT_NAME": "w", "PI_SUBAGENT_SESSION": str(self.session_file)}
        self.replay(self.open_loop("inline", "child"), env=env)
        link = tool_result("subagent", {}, "started", details={"id": "kid", "name": "w", "agent": "worker", "status": "started"})
        self.replay([*self.open_loop(), link, stage(stage="close", verdict="abandoned")])
        self.assertEqual(list(self.books.rglob("*")), [])

    def test_sweep_removes_empty_project_and_agents_directories(self):
        (self.books / "old-project" / "agents").mkdir(parents=True)
        (self.books / "other-project").mkdir()
        self.replay([{"event": "session_start", "payload": {}}])
        self.assertEqual(list(self.books.rglob("*")), [])


class TestCloseJudgment(BookCase):
    extensions = ("book.ts", "second-thought.ts")

    def test_jev_at_close_judges_the_loop_as_it_stood_when_close_ran_after_a_reflect_in_the_same_batch(self):
        close_call = {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "landed"}}}
        steps = [*self.open_loop(anchor="pytest -q"), edit(), bash_result("pytest -q", 0, "ok"), stage(stage="friction", tried="a", found="b"), close_call,
                 stage(stage="reflect", friction=[1], **{"class": "gap", "action": "solid-loop"}),
                 {**stage(stage="close", verdict="landed"), "emit": "c9"}]
        out = self.replay(steps, classify=jev_answers("advance", done=0.05))
        state = out["classifyCalls"][0]
        self.assertIn("1 recorded, 1 reflected", state["friction"])
        self.assertIn("[gap: solid-loop]", state["friction"])
        self.assertTrue(state["phase"].startswith("current: reflect; next: close"), state["phase"])
        self.assertTrue(out["emitted"][0]["content"][-1]["text"].startswith("\nJev:"))


class TestFreshReadJudging(PhaseCase):
    BRIEF = f"Parent action: wait\nRequested model: x\nRead {DIR}/spec.md and tell me what you find."

    def proposed(self) -> list[dict]:
        return [*self.open_loop("durable"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed"))]

    def test_jev_gets_the_brief_head_and_the_result_head_and_tail_without_host_boilerplate(self):
        self.replay(self.proposed())
        result = "Session: abc\nResume: x\n" + "A" * 1200 + "MIDDLE" + "B" * 3000 + "\nGaps: I guessed seven things."
        out = self.replay([subagent_result("scout", "fresh", result, self.BRIEF)], classify=answers(fresh_read=0.9))
        sent = out["classifyCalls"][0]
        self.assertEqual(sent["brief"], f"Read {DIR}/spec.md and tell me what you find.")
        self.assertNotIn("Session:", sent["result"])
        self.assertNotIn("MIDDLE", sent["result"])
        self.assertTrue(sent["result"].endswith("Gaps: I guessed seven things."))
        self.assertTrue(sent["result"].startswith("A" * 100))
        self.assertIn("phase read ✓ → approve", self.line([]))

    def test_a_not_fresh_verdict_shows_in_read_with_the_declare_hint(self):
        self.replay(self.proposed())
        self.replay([subagent_result("scout", "fresh", "I wrote some code", self.BRIEF)], classify=answers(fresh_read=0.1))
        text = self.read_text([])
        self.assertIn("fresh read by fresh judged not fresh — declare `fresh-read` if it was", text)
        self.replay([stage(stage="fresh-read")])
        self.assertNotIn("judged not fresh", self.read_text([]))

    def test_the_question_asks_only_whether_the_subagent_read_and_reported_on_the_spec(self):
        self.replay(self.proposed())
        out = self.replay([subagent_result("scout", "fresh", "x", self.BRIEF)], classify=answers(fresh_read=0.9))
        self.assertEqual(out["questionSets"], [["fresh_read"]])


class TestDurableVerify(PhaseCase):
    def ready(self) -> list[dict]:
        return [*self.open_loop("durable", anchor="pytest -q"), self.artifact("decision.md", DONE_ROWS), self.artifact("spec.md", spec_text("proposed")), stage(stage="fresh-read"),
                self.artifact("spec.md", spec_text("approved", True)), self.artifact("design.md", "## Approach\n\nUse the table.\n"), edit(), bash_result("pytest -q", 0, "ok")]

    def test_a_passing_anchor_alone_does_not_complete_a_durable_verify(self):
        line = self.line(self.ready())
        self.assertTrue(line.startswith("durable · phase act ✓ → verify (missing: docs/specs/2026-10-29-x/verification.md"), line)
        self.assertIn("a durable loop's verify also needs it", line)

    def test_verification_md_completes_it(self):
        line = self.line([*self.ready(), self.artifact("verification.md", "| Check | Result |\n|---|---|\n| a | pass |\n")])
        self.assertIn("phase verify ✓", line)


class TestTaskLines(BookCase):
    def test_read_shows_followup_when_set(self):
        todos = todo_state({"subject": "ship", "status": "pending", "metadata": {"followup": "MP-12"}}, {"subject": "plain", "status": "pending"})
        out = self.replay([todo_create("ship", followup="MP-12"), todo_create("plain", task_id=2), stage(stage="kind", kind="inline", intent="x"), {"branchAdd": [todos]}, stage(stage="read")])
        lines = text_of(out["results"][-1]).splitlines()
        self.assertIn("#1 pending ship — loop anchor — followup: MP-12", lines)
        self.assertIn("#2 pending plain — loop anchor", lines)

    def test_a_ref_to_a_file_that_is_not_markdown_is_shown_as_given(self):
        todos = todo_state({"subject": "t", "status": "pending", "metadata": {"ref": ["src/app.ts#L10", "src/util.py"]}})
        out = self.replay([todo_create("t", ref=["src/app.ts#L10", "src/util.py"]), stage(stage="kind", kind="inline", intent="x"), {"branchAdd": [todos]}, stage(stage="read")])
        text = text_of(out["results"][-1])
        self.assertIn("src/app.ts#L10, src/util.py", text)
        self.assertNotIn("→ missing", text)

    def test_relative_refs_resolve_against_the_loops_repos_as_well_as_the_cwd(self):
        other = self.cwd.parent / "other"
        init_repo(other)
        (other / "NOTES.md").write_text("# Top\n\n## Edge\n\nx\n")
        todos = todo_state({"subject": "t", "status": "pending"}, {"subject": "u", "status": "pending", "metadata": {"ref": "NOTES.md#Edge"}})
        out = self.replay([todo_create("t"), stage(stage="kind", kind="inline", intent="x"), edit(str(other / "lib.py")),
                           todo_create("u", task_id=2, ref="NOTES.md#Edge"), {"branchAdd": [todos]}, stage(stage="read")])
        self.assertIn("NOTES.md#Edge → L3-L5", text_of(out["results"][-1]))


if __name__ == "__main__":
    unittest.main()
