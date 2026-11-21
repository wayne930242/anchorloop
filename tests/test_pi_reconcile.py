"""How the book reconciles a long coordinator loop: ticket ids, units without an anchor of their own, friction counted once, and a
`read` summary that collapses children, landings, and review rounds the coordinator already handled (the MP Center book of 2026-11-20)."""

import json

from tests.pi_harness import stage, todo_create, todo_state, tool_call, tool_result
from tests.test_pi_book import edit, reviewer_result, text_of
from tests.test_pi_coordinator import CoordinatorCase, done_loop, returned, spawn

LOOP_ANCHOR = "pytest tests/mp4980"
GUARD = {"subject": "MP-4980 stateful guard", "status": "in_progress", "metadata": {"anchor": LOOP_ANCHOR, "kind": "inline", "agents": ["w1"]}}
BUILD = {"subject": "MP-3506 build", "status": "pending"}
DOCS = {"subject": "MP-3507 docs", "status": "pending"}


class ReconcileCase(CoordinatorCase):
    def creates(self, *tasks: dict) -> list[dict]:
        return [todo_create(task["subject"], i + 1, task["status"], **task.get("metadata", {})) for i, task in enumerate(tasks)]

    def child_edit(self, child: str, name: str) -> None:
        self.replay([tool_call("write", "src/app.py"), edit()], env={"PI_SUBAGENT_ID": child, "PI_SUBAGENT_NAME": name})

    def widget(self, branch: list) -> list[str]:
        out = self.replay([{"event": "session_start", "payload": {}}], branch=branch)
        return [item for item in out["widgets"] if item["key"] == "anchorloop"][-1]["lines"]

    def append_entries(self, *entries: dict) -> None:
        book = next(path for path in self.book_files() if "agents" not in path.parts)
        book.write_text(book.read_text() + "".join(f"- {json.dumps({'ts': '2026-11-20T00:00:00.000Z', **entry})}\n" for entry in entries))


class TestTicketIds(ReconcileCase):
    def test_a_host_name_or_a_dated_name_in_a_subject_is_no_ticket(self):
        self.git_repo()
        tasks = ({"subject": "Box watch (agent-tower-01)", "status": "pending"}, {"subject": "Cut release-1117 train", "status": "pending"}, GUARD,
                 {"subject": "MP-4367 view", "status": "pending", "metadata": {"anchor": "make test", "agents": ["w2"]}})
        steps = [*self.creates(*tasks), spawn("k3", "agent-tower-01-watch", task="watch agent-tower-01"), spawn("k4", "release-1117-gate", task="gate release-1117")]
        lines = self.read_text(steps, branch=[todo_state(*tasks)]).splitlines()
        self.assertFalse([line for line in lines if line.startswith(("TOWER-01", "RELEASE-1117", "#1 inline", "#2 inline"))], lines)
        self.assertTrue([line for line in lines if line.startswith("MP-4980 inline")], lines)

    def test_a_worker_named_after_a_hyphenated_ticket_still_binds_to_it(self):
        self.git_repo()
        one = {"subject": "MP-4366 export", "status": "in_progress", "metadata": {"anchor": "pytest -q", "kind": "inline"}}
        two = {"subject": "MP-4367 view", "status": "in_progress", "metadata": {"anchor": "make test", "kind": "inline"}}
        self.replay([*self.creates(one, two), spawn("k1", "fix-mp-4366-guard")], branch=[todo_state(one, two)])
        self.child_edit("k1", "fix-mp-4366-guard")
        lines = self.read_text([], branch=[todo_state(one, two)]).splitlines()
        self.assertIn("MP-4366 inline · act ✓ → verify (missing: a passing run of `pytest -q` after the last change, or `verify` with `task: 1`)", lines)
        self.assertIn("MP-4367 inline · anchor ✓ → act (missing: a change to the code)", lines)


    def test_a_subject_binds_an_uppercase_key_alone_or_before_a_hyphen_and_never_a_lowercase_or_zero_led_one(self):
        self.git_repo()
        meta = {"anchor": "make test", "kind": "inline"}
        tasks = ({"subject": "MP-4366 fix", "status": "pending", "metadata": meta}, {"subject": "MP-4367-followup", "status": "pending", "metadata": meta},
                 {"subject": "mp-4368 fix", "status": "pending", "metadata": meta}, {"subject": "MP-0123 pad", "status": "pending", "metadata": meta},
                 {"subject": "Box watch agent-tower-01", "status": "pending", "metadata": meta}, {"subject": "Cut release-1117", "status": "pending", "metadata": meta},
                 {"subject": "Read macq-1120 triage", "status": "pending", "metadata": meta})
        labels = [line.split(" inline")[0] for line in self.read_text(self.creates(*tasks), branch=[todo_state(*tasks)]).splitlines() if " inline ·" in line and not line.startswith("inline")]
        self.assertEqual(labels, ["MP-4366", "MP-4367", "#3", "#4", "#5", "#6", "#7"])


class TestOwnAnchor(ReconcileCase):
    def start(self) -> list:
        self.git_repo()
        branch = [todo_state(GUARD, BUILD, DOCS)]
        steps = [stage(stage="kind", kind="inline", intent="coordinate", anchor=LOOP_ANCHOR), *self.creates(GUARD, BUILD, DOCS),
                 spawn("k1", "w1"), spawn("k2", "mp3506-build"), spawn("k3", "mp3507-docs"), spawn("k9", "mp3506-check")]
        self.replay(steps, branch=branch)
        self.child_edit("k2", "mp3506-build")
        self.child_edit("k3", "mp3507-docs")
        return branch

    def test_a_unit_without_its_own_anchor_asks_for_one_instead_of_waiting_on_the_loop_anchor(self):
        branch = self.start()
        lines = self.read_text([], branch=branch).splitlines()
        self.assertIn("MP-3506 inline · start → anchor (missing: own anchor (metadata.anchor on todo #2))", lines)
        self.assertFalse([line for line in lines if line.startswith("MP-35") and LOOP_ANCHOR in line], lines)
        self.assertIn("#2 pending MP-3506 build — no own anchor", lines)

    def test_units_in_the_same_state_share_one_widget_row(self):
        branch = self.start()
        rows = self.widget(branch)
        self.assertIn("MP-3506, MP-3507 inline · start → anchor (missing: own anchor)", rows)
        self.assertEqual(len(rows), 3, rows)

    def test_a_child_of_a_unit_without_an_anchor_inherits_none(self):
        self.start()
        self.replay([{"event": "tool_call", "payload": {"toolName": "bash", "toolCallId": "c1", "input": {"command": LOOP_ANCHOR}}},
                     {"event": "tool_result", "payload": {"toolName": "bash", "toolCallId": "c1", "input": {"command": LOOP_ANCHOR}, "content": [{"type": "text", "text": "ok"}],
                                                          "isError": False, "structuredContent": {"exit_code": 0, "output": "ok"}}}],
                    env={"PI_SUBAGENT_ID": "k9", "PI_SUBAGENT_NAME": "mp3506-check"})
        child_books = [path for path in self.book_files() if "agents" in path.parts and "k9" in path.name]
        self.assertEqual(child_books, [])


class TestFrictionOnce(ReconcileCase):
    ONE = {"subject": "MP-4366 export", "status": "in_progress", "metadata": {"anchor": "pytest -q", "kind": "inline", "agents": ["w1"]}}
    TWO = {"subject": "MP-4367 view", "status": "in_progress", "metadata": {"anchor": "make test", "agents": ["w2"]}}

    def start(self) -> None:
        self.git_repo()
        self.replay([*self.creates(self.ONE, self.TWO), spawn("k1", "w1"), spawn("k2", "w2"), stage(stage="friction", tried="a", found="b")],
                    branch=[todo_state(self.ONE, self.TWO)])

    def test_a_unit_row_does_not_wait_on_the_loops_friction(self):
        self.start()
        self.child_edit("k1", "w1")
        lines = self.read_text([stage(stage="verify", note="ran it", task=1)], branch=[todo_state(self.ONE, self.TWO)]).splitlines()
        self.assertIn("MP-4366 inline · verify ✓ → close", lines)

    def test_the_loop_line_waits_on_the_friction_once_every_unit_is_done_and_a_skip_clears_it(self):
        self.start()
        self.child_edit("k1", "w1")
        self.child_edit("k2", "w2")
        branch = [todo_state(self.ONE, self.TWO)]
        lines = self.read_text([stage(stage="verify", note="ran it", task=1), stage(stage="verify", note="ran it", task=2)], branch=branch).splitlines()
        self.assertEqual(lines[0], "inline · phase verify ✓ → reflect (missing: 1 friction entry without a reflect)")
        self.assertEqual(sum("without a reflect" in line for line in lines), 1, lines)
        lines = self.read_text([stage(stage="skip", phase="reflect", reason="tool slip")], branch=branch).splitlines()
        self.assertTrue(lines[0].startswith("inline · phase verify ✓ → close"), lines[0])

    def test_close_names_the_friction_once_and_each_unit_once(self):
        self.start()
        done = [todo_state({**self.ONE, "status": "completed"}, {**self.TWO, "status": "completed"})]
        text = text_of(self.replay([stage(stage="close", verdict="landed")], branch=done)["results"][0])
        self.assertNotIn("reflect (", text)
        self.assertEqual(text.count("unreflected friction"), 1, text)
        self.assertEqual(text.count("MP-4366"), 1, text)
        self.assertIn("MP-4366 act, verify (a change to the code)", text)

    def test_close_leaves_out_a_unit_whose_todo_a_followup_defers(self):
        self.start()
        branch = [todo_state({**self.ONE, "status": "completed"}, {**self.TWO, "metadata": {**self.TWO["metadata"], "followup": "MP-9999"}})]
        text = text_of(self.replay([stage(stage="close", verdict="landed")], branch=branch)["results"][0])
        self.assertIn("MP-4366", text)
        self.assertNotIn("MP-4367", text)

    def skip_reflect(self, **args) -> tuple[str, str]:
        self.start()
        self.child_edit("k1", "w1")
        self.child_edit("k2", "w2")
        branch = [todo_state(self.ONE, self.TWO)]
        verified = [stage(stage="verify", note="ran it", task=1), stage(stage="verify", note="ran it", task=2)]
        out = self.replay([*verified, stage(stage="skip", phase="reflect", reason="tool slip", **args)], branch=branch)
        return text_of(out["results"][-1]), self.read_text([], branch=branch).splitlines()[0]

    def test_a_skip_of_reflect_without_a_task_counts_for_the_loop(self):
        said, line = self.skip_reflect()
        self.assertEqual(said, "ok")
        self.assertTrue(line.startswith("inline · phase verify ✓ → close"), line)

    def test_a_skip_of_reflect_with_the_first_unit_task_counts_for_the_loop_and_says_task_is_ignored(self):
        said, line = self.skip_reflect(task=1)
        self.assertIn("`task` is ignored", said)
        self.assertTrue(line.startswith("inline · phase verify ✓ → close"), line)

    def test_a_skip_of_reflect_with_the_last_unit_task_counts_for_the_loop(self):
        said, line = self.skip_reflect(task=2)
        self.assertIn("`task` is ignored", said)
        self.assertTrue(line.startswith("inline · phase verify ✓ → close"), line)

    def test_close_names_a_unit_parked_by_memory_that_acted_without_a_check(self):
        self.start()
        self.child_edit("k2", "w2")
        branch = [todo_state({**self.ONE, "status": "completed"}, {**self.TWO, "metadata": {**self.TWO["metadata"], "followup": "memory"}})]
        text = text_of(self.replay([stage(stage="close", verdict="landed")], branch=branch)["results"][0])
        self.assertIn("parked without check: MP-4367", text)

    def test_close_leaves_out_a_ticket_followup_even_after_a_change(self):
        self.start()
        self.child_edit("k2", "w2")
        branch = [todo_state({**self.ONE, "status": "completed"}, {**self.TWO, "metadata": {**self.TWO["metadata"], "followup": "MP-9999"}})]
        self.assertNotIn("parked without check", text_of(self.replay([stage(stage="close", verdict="landed")], branch=branch)["results"][0]))

    def test_a_reflect_recorded_after_close_is_read_back_with_its_class(self):
        self.start()
        late = {"type": "custom", "customType": "anchorloop-reflect", "data": {"friction": ["1"], "class": "gap", "action": "rule added"}}
        text = self.read_text([], branch=[todo_state(self.ONE, self.TWO), late])
        self.assertIn("friction: 1 (0 unreflected)", text)
        self.assertNotIn("without a reflect", text)

    def test_reflect_after_close_is_recorded_against_the_closed_loop(self):
        out = self.replay([*done_loop(self), stage(stage="friction", tried="a", found="b"), stage(stage="close", verdict="landed"),
                           stage(stage="reflect", friction=["1"], **{"class": "gap"}, action="rule added"), stage(stage="reflect", friction=["7"], **{"class": "gap"})])
        self.assertIn("`reflect` still takes these ids after the close", text_of(out["results"][-3]))
        self.assertIn("closed loop", text_of(out["results"][-2]))
        self.assertIn("unknown friction 7", out["results"][-1]["error"])
        recorded = [entry["data"] for entry in out["appended"] if entry["customType"] == "anchorloop-reflect"]
        self.assertEqual(recorded, [{"friction": ["1"], "class": "gap", "action": "rule added"}])


class TestLiveWidget(ReconcileCase):
    """The widget shows the work still in hand: a box main's book listed completed tickets as owing a verify (box friction F6, 2026-11-21)."""

    ONE = {"subject": "MP-4366 export", "status": "in_progress", "metadata": {"anchor": "pytest -q", "kind": "inline", "agents": ["w1"]}}
    TWO = {"subject": "MP-4367 view", "status": "in_progress", "metadata": {"anchor": "filtered view tests pass", "kind": "inline", "agents": ["w2"]}}

    def start(self) -> None:
        self.git_repo()
        self.replay([*self.creates(self.ONE, self.TWO), spawn("k1", "w1"), spawn("k2", "w2")], branch=[todo_state(self.ONE, self.TWO)])
        self.child_edit("k1", "w1")
        self.child_edit("k2", "w2")

    def test_a_completed_unit_leaves_the_widget_and_the_loop_line_follows_the_open_one(self):
        self.start()
        branch = [todo_state({**self.ONE, "status": "completed"}, self.TWO)]
        rows = self.widget(branch)
        self.assertFalse([row for row in rows if row.startswith("MP-4366")], rows)
        self.assertIn("MP-4367 inline · act ✓ → verify (missing: anchor run or verify)", rows)
        self.assertTrue(self.read_text([], branch=branch).startswith("inline · phase act ✓ → verify (missing: a passing run of `filtered view tests pass`"))
        # Once no open unit owes anything, the loop line names what the completed one left unproved, as the close will.
        lines = self.read_text([stage(stage="verify", note="view tests passed", task=2)], branch=branch).splitlines()
        self.assertEqual(lines[0], "inline · phase act ✓ → verify (missing: a passing run of `pytest -q` after the last change, or `verify` with `task: 1`)")

    def test_a_units_prose_anchor_is_closed_by_a_declared_verify_with_its_task(self):
        self.start()
        branch = [todo_state(self.ONE, self.TWO)]
        self.assertIn("MP-4366, MP-4367 inline · act ✓ → verify (missing: anchor run or verify)", self.widget(branch))
        lines = self.read_text([stage(stage="verify", note="filtered view tests passed in w2's worktree", task=2)], branch=branch).splitlines()
        self.assertIn("MP-4367 inline · verify ✓ → close", lines)


class TestReadSummary(ReconcileCase):
    def test_children_that_returned_share_one_line_and_view_all_keeps_each(self):
        self.git_repo()
        self.replay([*done_loop(self), spawn("k1", "w1"), spawn("k2", "w2")])
        self.child_edit("k1", "w1")
        self.child_edit("k2", "w2")
        self.replay([returned("w1"), returned("w2")])
        text = self.read_text([])
        self.assertNotIn("child w1:", text)
        self.assertIn("children returned: 2 (ok 2, failed 0) (`read` with view", text)
        full = text_of(self.replay([stage(stage="read", view="all")])["results"][-1])
        self.assertIn("child w1:", full)

    def test_jevs_snapshot_counts_returned_children_by_state_without_the_read_hint(self):
        self.git_repo()
        self.replay([*done_loop(self), spawn("k1", "w1"), spawn("k2", "w2")])
        self.child_edit("k1", "w1")
        self.child_edit("k2", "w2")
        self.replay([returned("w1"), returned("w2", exitCode=1)])
        close = {"event": "tool_call", "payload": {"toolName": "anchorloop_stage", "toolCallId": "c9", "input": {"stage": "close", "verdict": "abandoned"}}}
        answers = {"move": {"type": "choice", "choice": "advance", "probabilities": {"advance": 0.7}}, "done": {"type": "bool", "probability": 0.9},
                   "review": {"type": "choice", "choice": "none", "probabilities": {"none": 0.6}}, "quality": {"type": "score", "score": 2.9}}
        out = self.replay([close, stage(stage="close", verdict="abandoned"), tool_result("anchorloop_stage", {"stage": "close"}, "closed", call_id="c9")],
                          branch=[todo_state({"subject": "unit", "status": "completed"})], extensions=("book.ts", "second-thought.ts"), classify={"stopReason": "stop", "answers": answers})
        verify = out["classifyCalls"][0]["verify"]
        self.assertIn("children returned: 2 (ok 1, failed 1)", verify)
        self.assertNotIn('view "all"', verify)

    def test_a_child_still_out_shares_one_out_line(self):
        text = self.read_text([*done_loop(self), spawn("k1", "w1", "/s/none.jsonl"), spawn("k2", "w2", "/s/two.jsonl")])
        self.assertIn("out (no result yet): w1 (process unknown), w2 (process unknown)", text)
        self.assertNotIn("w1: no result", text)

    def test_only_the_newest_landings_are_listed(self):
        self.replay(done_loop(self))
        self.append_entries(*({"stage": "land", "label": f"w{n}", "ref": "origin/main", "rule": "ancestor", "verified": True, "head": f"{n:040d}"} for n in range(8)))
        text = self.read_text([])
        landed = [line for line in text.splitlines() if line.startswith("landed w")]
        self.assertEqual([line.split()[1] for line in landed], ["w3", "w4", "w5", "w6", "w7"])
        self.assertIn("landed: 3 earlier", text)

    def test_a_reviewer_or_a_landed_worker_gets_no_behind_note(self):
        self.shared_repo()
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        self.advance_origin(2)
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        self.replay([*done_loop(self), spawn("kr", "mp4367-review", worktree=worktree, agent="reviewer"), spawn("kw", "mp4367-worker", worktree=worktree)])
        self.assertIn("mp4367-worker based 2 behind", self.read_text([]))
        self.append_entries({"stage": "land", "child": "kw", "label": "mp4367-worker", "ref": "origin/main", "rule": "ancestor", "verified": True, "head": "f" * 40})
        text = self.read_text([])
        self.assertNotIn("behind", text)

    def test_the_review_trend_names_the_count_and_the_last_three_rounds(self):
        rounds = [reviewer_result(f"Round {n}.\nBlocking: P0=0 P1={n}") for n in (5, 4, 3, 2, 1)]
        text = self.read_text([*self.open_loop("reviewed"), *rounds])
        self.assertIn("reviews: 5 round(s): … → blocking P0=0 P1=3 → blocking P0=0 P1=2 → blocking P0=0 P1=1;", text)
