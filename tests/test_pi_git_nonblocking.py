"""The book's git reads run off the event loop: a slow git delays the handlers pi awaits, never pi's other timers, and records the same book."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.pi_harness import PI_DIR, SETTLE, bash_call, bash_result, parallel, run, stage, todo_create, tool_call, tool_result
from tests.test_pi_coordinator import CoordinatorCase, returned, spawn

BOOK_TS = Path(__file__).resolve().parent.parent / "pi" / "support" / "book.ts"

# A git call takes this long under the slow wrapper; a handler that waits for git synchronously holds pi's timers back as long.
SLOW_SECONDS = 1
# How late a 20 ms timer may fire while a step runs: well below one slow git call.
LAG_LIMIT_MS = 200


class TestGitOffTheEventLoop(CoordinatorCase):
    extensions = ("book.ts", "anchor-gate.ts", "second-thought.ts")

    def slow_git(self, seconds: float = SLOW_SECONDS) -> dict:
        """A `git` first on PATH that sleeps before running the real git."""
        bin_dir = self.root / "slow-bin"
        bin_dir.mkdir(exist_ok=True)
        script = bin_dir / "git"
        script.write_text(f'#!/bin/sh\nsleep {seconds}\nexec {shutil.which("git")} "$@"\n')
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

    def test_parallel_handlers_in_two_copies_of_the_modules_record_as_one_at_a_time(self):
        # RV-F003: a bash result's landing check (book.ts), a worker's result (book.ts message_end, RV-F002), and a settle's
        # (second-thought.ts, loaded from a copy of pi/, so it has its own copy of every support module) run at once; the lock both
        # copies share makes them read and write the book in turn.
        self.shared_repo()
        base = self.sh("rev-parse", "HEAD")
        tree = self.worktree()
        self.commit_in(tree)
        copy = self.root / "pi-copy"
        shutil.copytree(PI_DIR, copy)
        extensions = ("book.ts", "anchor-gate.ts", copy / "second-thought.ts")
        real = shutil.which("git")
        worktree = {"path": str(tree), "branch": "feature", "baseRef": "HEAD", "baseSha": base}
        before = [
            stage(stage="kind", kind="inline", intent="coordinate", anchor="python3 -c pass"),
            todo_create("unit", observe=["export page loads"]),
            tool_call("write", "app.py", call_id="w1"),
            tool_result("write", {"path": "app.py"}, call_id="w1"),
            spawn("kid", "w1", worktree=worktree),
            run(real, "push", "-q", "origin", "feature:main", where=str(tree)),
            run(real, "fetch", "-q", "origin"),
        ]
        together = [bash_result("python3 -c pass", 0), returned("w1"), SETTLE]
        slow = self.slow_git(0.2)
        self.replay([*before, parallel(*together)], env=slow, classify="missing", extensions=extensions)
        at_once = self.without_times(self.book()[1])
        self.assertEqual([entry["stage"] for entry in at_once].count("land"), 1, "the landing was recorded once per handler")

        shutil.rmtree(self.books)
        self.sh("update-ref", "refs/heads/main", base, where=self.root / "remote.git")
        self.sh("update-ref", "refs/remotes/origin/main", base)
        self.replay([*before, *together], env=slow, classify="missing", extensions=extensions)
        self.assertEqual(at_once, self.without_times(self.book()[1]))


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extensions")
class TestReadPasses(unittest.TestCase):
    """RV-F004: a `read` whose pass needs many git answers asks for them together, so the pass runs a fixed number of times."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve() / "repo"
        self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        (self.repo / "base.txt").write_text("base\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "base.txt"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True, capture_output=True)

    def tearDown(self):
        self.temp.cleanup()

    def passes(self, body: str) -> dict:
        """Runs `body` (an expression over `repo`) inside `read`; what it returned and how many passes it took."""
        support = BOOK_TS.parent
        code = (f'import {{ contentHashes, read }} from "{(support / "book.ts").as_uri()}";'
                f' import {{ orphanLines }} from "{(support / "orphans.ts").as_uri()}";'
                f' const repo = {json.dumps(str(self.repo))}; let passes = 0;'
                f' const value = await read(() => {{ passes++; return {body}; }}); console.log(JSON.stringify({{ value, passes }}));')
        env = {**os.environ, "ANCHORLOOP_GIT_TIMEOUT_MS": "120000"}
        proc = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_hashing_paths_alone_after_a_failed_batch_takes_one_more_pass_not_one_per_path(self):
        (self.repo / "sub").mkdir()
        names = ["sub", *[f"f{i}.txt" for i in range(12)]]
        for name in names[1:]:
            (self.repo / name).write_text(f"{name}\n")
        got = self.passes(f"contentHashes(repo, {json.dumps(names)})")
        self.assertEqual(got["value"]["sub"], "unknown")
        self.assertTrue(all(len(got["value"][name]) == 40 for name in names[1:]), got["value"])
        # The batch, the paths alone, and the pass that has them all.
        self.assertEqual(got["passes"], 3)

    def test_orphan_lines_ask_every_worktree_count_in_one_pass(self):
        head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        # Each child works in its own directory, so each count is a git call of its own.
        for i in range(6):
            (self.repo / f"d{i}").mkdir()
        links = [{"stage": "link", "ts": "2026-11-23T00:00:00Z", "child": f"kid{i}", "name": f"w{i}", "cwd": str(self.repo),
                  "worktree": {"path": str(self.repo / f"d{i}"), "branch": f"b{i}", "baseSha": head}} for i in range(6)]
        got = self.passes(f"orphanLines({json.dumps(links)})")
        self.assertEqual(len(got["value"]), 6)
        self.assertTrue(all(line.endswith("ahead 0") for line in got["value"]), got["value"])
        # The pass that asks for every count, and the pass that has them, where liveness runs once per child.
        self.assertEqual(got["passes"], 2)


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extensions")
class TestGitAsyncTimeout(unittest.TestCase):
    def test_a_git_whose_grandchild_keeps_stdout_open_settles_at_the_timeout(self):
        # RV-F001: a wrapper that leaves a process holding the pipe must not hold the call (and the book lock) past the timeout.
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = Path(temp)
            script = bin_dir / "git"
            script.write_text("#!/bin/sh\n(sleep 5) &\nexec sleep 10\n")
            script.chmod(0o755)
            code = (f'import {{ gitAsync }} from "{BOOK_TS.as_uri()}"; const start = performance.now();'
                    ' const out = await gitAsync(process.cwd(), ["rev-parse", "HEAD"]);'
                    ' console.log(JSON.stringify({ out: out ?? null, ms: Math.round(performance.now() - start) }));')
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "ANCHORLOOP_GIT_TIMEOUT_MS": "1000"}
            began = time.monotonic()
            proc = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, env=env, cwd=temp, timeout=30)
            elapsed = time.monotonic() - began
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertIsNone(got["out"])
        self.assertLess(got["ms"], 2000, "gitAsync waited for the process holding stdout")
        self.assertLess(elapsed, 4, "node stayed alive after gitAsync gave up on git")
