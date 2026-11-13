"""Reading linked child books costs one index of the books root per event, not one scan per link (anchorloop#19)."""

import json
import time
from pathlib import Path

from tests.pi_harness import bash_result, tool_result
from tests.test_pi_book import BookCase

# Counts the directory listings and file reads under the books root that one replay makes, written out when Node exits.
COUNTER = """
import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
const root = process.env.ANCHORLOOP_BOOKS_DIR;
const counts = { readdir: 0, read: 0 };
const under = (path) => String(path).startsWith(root);
const { readdirSync, readFileSync, writeFileSync } = fs;
fs.readdirSync = function (path, ...rest) { if (under(path)) counts.readdir++; return readdirSync.call(this, path, ...rest); };
fs.readFileSync = function (path, ...rest) { if (under(path)) counts.read++; return readFileSync.call(this, path, ...rest); };
syncBuiltinESMExports();
process.on("exit", () => writeFileSync(process.env.ANCHORLOOP_TEST_COUNTS, JSON.stringify(counts)));
"""

PROJECTS = 120
LINKS = 60


def child_book(child: str, *entries: dict) -> str:
    header = {"id": f"{child}-0000", "owner": child, "session": None, "cwd": "/nowhere", "opened": "2026-11-13T00:00:00.000Z"}
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
            (agents / f"c{i}.yml").write_text(child_book(f"c{i}", *entries))
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
