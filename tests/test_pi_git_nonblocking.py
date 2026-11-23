"""The book's git reads run off the event loop: a slow git delays the handlers pi awaits, never pi's other timers, and records the same book."""

import shutil

from tests.pi_harness import SETTLE, bash_call, bash_result, run, stage, todo_create, tool_call, tool_result
from tests.test_pi_coordinator import CoordinatorCase, returned, spawn

# A git call takes this long under the slow wrapper; a handler that waits for git synchronously holds pi's timers back as long.
SLOW_SECONDS = 1
# How late a 20 ms timer may fire while a step runs: well below one slow git call.
LAG_LIMIT_MS = 200


class TestGitOffTheEventLoop(CoordinatorCase):
    extensions = ("book.ts", "anchor-gate.ts", "second-thought.ts")

    def slow_git(self) -> dict:
        """A `git` first on PATH that sleeps before running the real git."""
        bin_dir = self.root / "slow-bin"
        bin_dir.mkdir(exist_ok=True)
        script = bin_dir / "git"
        script.write_text(f'#!/bin/sh\nsleep {SLOW_SECONDS}\nexec {shutil.which("git")} "$@"\n')
        script.chmod(0o755)
        return {"PATH": f"{bin_dir}:{self.env()['PATH']}"}

    def steps(self) -> list[dict]:
        """A coordinator loop that builds trees, links a worker and a reviewer, runs its anchor, and sees the worker's branch land."""
        real = shutil.which("git")
        tree = self.worktree()
        base = self.sh("rev-parse", "HEAD")
        self.commit_in(tree)
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        return [
            stage(stage="kind", kind="inline", intent="coordinate", anchor="python3 -c pass"),
            todo_create("unit", observe=["export page loads"]),
            tool_call("write", "app.py", call_id="w1"),
            tool_result("write", {"path": "app.py"}, call_id="w1"),
            spawn("kid", "w1", worktree=worktree),
            spawn("rev", "r1", agent="reviewer"),
            bash_call("python3 -c pass", call_id="b1"),
            bash_result("python3 -c pass", 0),
            SETTLE,
            run(real, "push", "-q", "origin", "feature:main", where=str(tree)),
            run(real, "fetch", "-q", "origin"),
            returned("w1"),
            stage(stage="read"),
        ]

    @staticmethod
    def without_times(entries: list[dict]) -> list[dict]:
        return [{key: value for key, value in entry.items() if key not in ("ts", "from")} for entry in entries]

    def test_a_slow_git_leaves_the_event_loop_free_and_records_the_same_book(self):
        self.shared_repo()
        base = self.sh("rev-parse", "HEAD")
        steps = self.steps()
        slow = self.replay(steps, env=self.slow_git(), classify="missing")
        timed = [(index, lag) for index, (step, lag) in enumerate(zip(steps, slow["lags"])) if "exec" not in step and "file" not in step]
        late = [(index, steps[index].get("event") or steps[index].get("tool"), lag) for index, lag in timed if lag >= LAG_LIMIT_MS]
        self.assertEqual(late, [], f"steps that held the event loop (step, event, ms): {late}")
        slow_entries = self.without_times(self.book()[1])
        self.assertIn("land", [entry["stage"] for entry in slow_entries], "the worker's landing was not recorded")
        self.assertTrue(any(entry["stage"] == "verify" and "treeAt" in entry for entry in slow_entries), "the anchor run recorded no tree")
        self.assertTrue(any(entry["stage"] == "link" and "treeAt" in entry for entry in slow_entries), "the reviewer link recorded no tree")

        # The same replay with git at full speed, from the same repo state, writes the same book.
        shutil.rmtree(self.books)
        self.sh("update-ref", "refs/heads/main", base, where=self.root / "remote.git")
        self.sh("update-ref", "refs/remotes/origin/main", base)
        fast = self.replay(steps, classify="missing")
        self.assertEqual(self.without_times(self.book()[1]), slow_entries)
        read = lambda out: [line for line in "\n".join(block["text"] for block in out["results"][-1]["content"]).splitlines() if not line.startswith("book: ")]
        self.assertEqual(read(fast), read(slow))
