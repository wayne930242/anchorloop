"""Reading linked child books costs one index of the books root per event, not one scan per link (anchorloop#19)."""

import json
import subprocess
import time
from pathlib import Path

from tests.pi_harness import PI_DIR, bash_result, stage, tool_call, tool_result
from tests.test_pi_book import BookCase, subagent_result

# Counts the directory listings and file reads under the books root that one replay makes, written out when Node exits.
COUNTER = """
import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
const root = process.env.ANCHORLOOP_BOOKS_DIR;
const counts = { readdir: 0, read: 0, git: 0 };
const under = (path) => String(path).startsWith(root);
const { readdirSync, readFileSync, writeFileSync } = fs;
fs.readdirSync = function (path, ...rest) { if (under(path)) counts.readdir++; return readdirSync.call(this, path, ...rest); };
fs.readFileSync = function (path, ...rest) { if (under(path)) counts.read++; return readFileSync.call(this, path, ...rest); };
const cp = process.getBuiltinModule("node:child_process");
const { execFileSync } = cp;
cp.execFileSync = function (file, ...rest) { if (file === "git") counts.git++; return execFileSync.call(this, file, ...rest); };
syncBuiltinESMExports();
process.on("exit", () => writeFileSync(process.env.ANCHORLOOP_TEST_COUNTS, JSON.stringify(counts)));
"""

PROJECTS = 120
LINKS = 60


def child_book(child: str, *entries: dict, cwd: str | None = None) -> str:
    header = {"id": f"{child}-0000", "owner": child, "session": None, "cwd": cwd or f"/nowhere/{child}", "opened": "2026-11-13T00:00:00.000Z"}
    lines = ["# anchorloop loop book", *(f"{key}: {json.dumps(value)}" for key, value in header.items()), "entries:"]
    lines += [f"- {json.dumps({'ts': '2026-11-13T00:00:01.000Z', **entry})}" for entry in entries]
    return "\n".join(lines) + "\n"


class TestChildBookReads(BookCase):
    def populate(self) -> int:
        """Many project dirs, a main book linking many children, and child books with friction; returns the friction left to reflect."""
        self.replay(self.open_loop(anchor="pytest -q"))
        main = self.book_files()[0]
        with main.open("a") as book:
            for i in range(LINKS):
                book.write("- " + json.dumps({"ts": "2026-11-13T00:00:02.000Z", "stage": "link", "child": f"c{i}", "name": f"w{i}"}) + "\n")
        for p in range(PROJECTS):
            (self.books / f"p{p:03d}" / "agents").mkdir(parents=True)
        # Each child works in its own existing directory (as live worktrees do), so no two share a root lookup.
        cwds = Path(self.temp_dir.name) / "cwds"
        for i in range(LINKS):
            (cwds / f"c{i}").mkdir(parents=True)
        open_friction = 0
        for i in range(LINKS):
            agents = self.books / f"p{i % PROJECTS:03d}" / "agents"
            entries = [{"stage": "kind", "kind": "inline", "intent": "x"}]
            if i % 3 == 0:
                entries.append({"stage": "friction", "id": 1, "tried": "a", "found": "b", "led_by": "none"})
                open_friction += 1
            if i % 6 == 0:
                entries.append({"stage": "reflect", "friction": ["1"], "class": "resolved"})
                open_friction -= 1
            (agents / f"c{i}.yml").write_text(child_book(f"c{i}", *entries, cwd=str(cwds / f"c{i}")))
            if i % 10 == 0:
                # An earlier closed loop of the child, and a second book of it in another project.
                (agents / f"c{i}.closed-1.yml").write_text(child_book(f"c{i}", {"stage": "friction", "id": 1, "tried": "a", "found": "b", "led_by": "none"}))
                (self.books / f"p{(i + 1) % PROJECTS:03d}" / "agents" / f"c{i}.yml").write_text(child_book(f"c{i}", {"stage": "friction", "id": 1, "tried": "a", "found": "b", "led_by": "none"}))
                open_friction += 2
        return open_friction

    def counted(self, steps: list[dict]) -> tuple[dict, dict, float]:
        counter = Path(self.temp_dir.name) / "counter.mjs"
        counter.write_text(COUNTER)
        counts = Path(self.temp_dir.name) / "counts.json"
        env = {"NODE_OPTIONS": f"--import={counter.as_uri()}", "ANCHORLOOP_TEST_COUNTS": str(counts)}
        started = time.monotonic()
        out = self.replay(steps, env=env)
        return out, json.loads(counts.read_text()), time.monotonic() - started

    def test_a_tool_result_indexes_the_books_root_once_however_many_children_are_linked(self):
        open_friction = self.populate()
        out, counts, elapsed = self.counted([tool_result("read", {"path": "app.py"}), bash_result("ls", 0, "app.py")])
        # Two events: each lists the root and every project's agents dir at most once, plus the main book's own reads.
        self.assertLessEqual(counts["readdir"], 2 * (PROJECTS + 1) + 4, counts)
        child_files = LINKS + 2 * (LINKS // 10)
        self.assertLessEqual(counts["read"], 2 * (child_files + 10), counts)
        widget = [w for w in out["widgets"] if w["key"] == "anchorloop" and w["lines"]][-1]["lines"][0]
        self.assertTrue(widget.endswith(f" · {open_friction} friction"), widget)
        self.assertLess(elapsed, 30, "a replay over many linked children stalls")

    def bounded(self, steps: list[dict], passes: int = 2) -> dict:
        """Replays one event over the populated root and asserts it lists and reads the root a bounded number of times."""
        self.populate()
        out, counts, elapsed = self.counted(steps)
        child_files = LINKS + 2 * (LINKS // 10)
        # One index (the root and every agents dir) plus the main book's own reads; a handful of events' worth of slack, never links x projects.
        self.assertLessEqual(counts["readdir"], passes * (PROJECTS + 1) + 10, counts)
        self.assertLessEqual(counts["read"], passes * (child_files + 10), counts)
        self.assertLess(elapsed, 30, counts)
        return {"out": out, "counts": counts}

    def test_b_a_write_event_indexes_once(self):
        self.extensions = ("book.ts", "anchor-gate.ts")
        self.bounded([tool_call("write", "src/app.py")])

    def test_c_a_worker_result_indexes_once_and_spawns_git_once_per_repo(self):
        # The children's directories are all distinct and exist: a git spawn per child directory would be LINKS spawns.
        got = self.bounded([subagent_result("worker", "w0", "done")])
        self.assertLessEqual(got["counts"]["git"], 12, got["counts"])

    def test_c2_a_reviewer_result_spawns_git_boundedly(self):
        got = self.bounded([subagent_result("reviewer", "w0", "P0=0 P1=0")])
        self.assertLessEqual(got["counts"]["git"], 12, got["counts"])

    def test_d_closing_a_loop_indexes_once(self):
        got = self.bounded([stage(stage="close", verdict="abandoned")])
        self.assertEqual(self.book_files(), [], got["out"]["results"])

    def test_e_session_start_indexes_once(self):
        # The start-up sweep of the books root lists each project dir itself, on top of the one child-book index.
        self.bounded([{"event": "session_start", "payload": {}}], passes=4)

    def test_f_a_child_book_change_inside_one_event_is_seen(self):
        self.populate()
        script = """
import { registerHooks } from "node:module";
registerHooks({ resolve: (s, c, next) => s === "@earendil-works/pi-coding-agent" ? { url: "data:text/javascript," + encodeURIComponent("export function parseSkillBlock(){return null}"), shortCircuit: true } : next(s, c) });
const book = await import(process.argv[1]);
const main = book.parseBook(process.argv[2]);
const out = {};
book.withTrees(() => {
  const count = () => book.allFriction(main.entries).length;
  out.before = count();
  out.again = count();
  const child = book.findChildBooks("c1")[0].book;
  book.appendEntry(child.path, "friction", { id: 9, tried: "a", found: "b", led_by: "none" });
  out.appended = count();
  book.deleteBook(book.findChildBooks("c1")[0].book.path);
  out.deleted = count();
  out.children = book.findChildBooks("c1").length;
});
console.log(JSON.stringify(out));
"""
        proc = subprocess.run(["node", "--input-type=module", "-e", script, (PI_DIR / "support" / "book.ts").as_uri(), str(next(f for f in self.book_files() if f.name == "sess-1.yml"))], capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(got["again"], got["before"])
        self.assertEqual(got["appended"], got["before"] + 1, got)
        self.assertLess(got["deleted"], got["appended"])
        self.assertEqual(got["children"], 0)

    def test_g_the_root_found_without_git_is_the_root_git_reports(self):
        base = Path(self.temp_dir.name) / "roots"
        plain = base / "plain" / "sub"
        plain.mkdir(parents=True)
        repo = base / "repo"
        (repo / "a" / "b").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "f").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "f"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "m"], check=True)
        tree = base / "tree"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach", str(tree)], check=True)
        (tree / "deep").mkdir()
        paths = [plain / "_", repo / "_", repo / "a" / "b" / "_", repo / "gone" / "x" / "_", tree / "_", tree / "deep" / "_", repo / ".git" / "_", base / "_"]
        script = """
import { registerHooks } from "node:module";
registerHooks({ resolve: (s, c, next) => s === "@earendil-works/pi-coding-agent" ? { url: "data:text/javascript," + encodeURIComponent("export function parseSkillBlock(){return null}"), shortCircuit: true } : next(s, c) });
const book = await import(process.argv[1]);
console.log(JSON.stringify(process.argv.slice(2).map((p) => book.repoRootOf(p) ?? null)));
"""
        proc = subprocess.run(["node", "--input-type=module", "-e", script, (PI_DIR / "support" / "book.ts").as_uri(), *map(str, paths)], capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for path, ours in zip(paths, json.loads(proc.stdout.strip().splitlines()[-1])):
            near = path.parent
            while not near.exists():
                near = near.parent
            asked = subprocess.run(["git", "-C", str(near), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
            theirs = str(Path(asked.stdout.strip()).resolve()) if asked.returncode == 0 else None
            self.assertEqual(ours, theirs, path)
