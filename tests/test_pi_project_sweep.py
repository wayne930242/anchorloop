"""Issue #19 leftover: the project dirs of removed checkouts are swept from the books root, at most once a day, at session start.

A project dir goes only when its source path is gone, no book under it is an open loop or has a dispatch still out, nothing under it
was written for a week, and it is not the session's own project. What goes is logged. Every test runs in a temp books root."""

import json
import os
import re
import time
import unittest
from pathlib import Path

from tests.test_pi_book import BookCase

DAY = 24 * 60 * 60
START = {"event": "session_start", "payload": {}}


def old(path: Path, days: float = 10) -> None:
    stamp = time.time() - days * DAY
    os.utime(path, (stamp, stamp))


class SweepCase(BookCase):
    def write_book(self, path: Path, cwd: str, *entries: dict, session: str | None = None) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# anchorloop loop book", f'id: "{path.stem}"', f"owner: {json.dumps('main')}", f"session: {json.dumps(session)}", f"cwd: {json.dumps(cwd)}", "entries:", *[f"- {json.dumps(e)}" for e in entries]]
        path.write_text("\n".join(lines) + "\n")
        return path

    def gone(self, name: str = "removed-worktree") -> str:
        """A source path that no longer exists."""
        return str(self.cwd.parent / name)

    def project(self, slug: str, cwd: str, *entries: dict, days: float = 10, child: bool = False, name: str = "book") -> Path:
        """A project dir holding one book written `days` ago; returns the dir."""
        dir = self.books / slug
        path = self.write_book(dir / "agents" / f"{name}.yml" if child else dir / f"{name}.yml", cwd, *entries)
        old(path, days)
        return dir

    def parent(self, *kids: str, closed: bool = True) -> None:
        """A living main session of a project that exists, linking `kids`: the book sweep keeps a linked child book however old it is."""
        book = self.write_book(self.books / "parent-project" / "parent.yml", str(self.cwd), OPEN, *[{"stage": "link", "child": kid} for kid in kids], *([CLOSED] if closed else []), session=str(self.session_file))
        os.utime(book, None)

    def stamp(self) -> Path:
        # Beside the books root, so it never looks like a project dir.
        return self.books.parent / "books-sweep.stamp"

    def log(self) -> str:
        path = self.books.parent / "books-sweep.log"
        return path.read_text() if path.exists() else ""

    def start(self) -> dict:
        return self.replay([START])

    def own_slug(self) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", str(self.cwd.resolve())).strip("-")[-80:]


CLOSED = {"stage": "close", "verdict": "landed"}
OPEN = {"stage": "kind", "kind": "inline", "intent": "still going"}


class TestProjectSweep(SweepCase):
    def test_a_dir_of_a_removed_path_with_closed_old_books_is_swept_and_logged(self):
        self.parent("kid")
        dir = self.project("gone-one", self.gone(), OPEN, CLOSED, child=True, name="kid")
        out = self.start()
        self.assertTrue((self.books / "parent-project" / "parent.yml").exists())
        self.assertFalse(dir.exists())
        self.assertIn("gone-one", self.log())
        self.assertIn(self.gone(), self.log())
        (notice,) = out["notices"]
        self.assertIn("1 stale project dir removed", notice["message"])

    def test_a_dir_whose_child_book_an_unclosed_main_links_is_kept(self):
        # The main lives elsewhere and still reads this child's friction and edits, so its dir stays though it is old and its path is gone.
        self.parent("kid", closed=False)
        dir = self.project("linked-one", self.gone(), OPEN, CLOSED, child=True, name="kid", days=30)
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())
        self.assertEqual(self.log(), "")

    def test_the_dir_goes_once_the_linking_main_is_closed(self):
        self.parent("kid", closed=False)
        dir = self.project("linked-two", self.gone(), OPEN, CLOSED, child=True, name="kid", days=30)
        self.start()
        self.assertTrue(dir.exists())
        self.parent("kid", closed=True)
        old(self.stamp(), 2)
        self.start()
        self.assertFalse(dir.exists())
        self.assertIn("linked-two", self.log())

    def test_a_dir_whose_source_path_still_exists_is_kept(self):
        live = self.cwd.parent / "live-checkout"
        live.mkdir()
        self.parent("kid")
        dir = self.project("live-one", str(live), CLOSED, child=True, name="kid")
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())
        self.assertEqual(self.log(), "")

    def test_a_dir_with_an_open_loop_is_kept_though_its_path_is_gone_and_it_is_old(self):
        # A linked child book survives the book sweep however old it is; it is not closed, so its loop is open.
        self.parent("kid")
        dir = self.project("open-one", self.gone(), OPEN, child=True, name="kid", days=30)
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())
        self.assertEqual(self.log(), "")

    def test_a_dir_with_a_dispatch_still_out_is_kept(self):
        # The child book is closed, but its own last link has no result and the grandchild's host cannot say it is gone.
        self.parent("kid")
        link = {"stage": "link", "child": "grandkid", "cwd": self.gone("kid-tree")}
        dir = self.project("out-one", self.gone(), link, CLOSED, days=30, child=True, name="kid")
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())

    def test_a_dir_written_within_the_week_is_kept(self):
        self.parent("kid")
        dir = self.project("recent-one", self.gone(), CLOSED, days=3, child=True, name="kid")
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())

    def test_one_recent_file_keeps_the_whole_dir(self):
        self.parent("kid", "late")
        dir = self.project("mixed-one", self.gone(), CLOSED, days=30, child=True, name="kid")
        self.write_book(dir / "agents" / "late.yml", self.gone(), CLOSED)
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())

    def test_the_current_projects_dir_is_never_touched(self):
        self.parent("kid")
        dir = self.project(self.own_slug(), self.gone(), CLOSED, days=30, child=True, name="kid")
        self.start()
        self.assertTrue((dir / "agents" / "kid.yml").exists())
        self.assertEqual(self.log(), "")

    def test_a_dir_with_no_recorded_source_path_is_kept(self):
        self.parent("kid")
        dir = self.books / "unknown-one"
        path = dir / "agents" / "kid.yml"
        path.parent.mkdir(parents=True)
        path.write_text('# anchorloop loop book\nid: "kid"\nsession: null\nentries:\n- {"stage":"close","verdict":"landed"}\n')
        old(path, 30)
        self.start()
        self.assertTrue(path.exists())

    def test_a_dir_holding_a_book_that_cannot_be_read_is_kept(self):
        self.parent("kid", "blocked")
        dir = self.project("unreadable-one", self.gone(), CLOSED, days=30, child=True, name="kid")
        blocked = dir / "agents" / "blocked.yml"
        old(self.write_book(blocked, self.gone(), CLOSED), 30)
        blocked.chmod(0)
        try:
            self.start()
            self.assertTrue((dir / "agents" / "kid.yml").exists())
        finally:
            blocked.chmod(0o644)

    def test_the_sweep_runs_once_a_day(self):
        self.parent("one", "two")
        first = self.project("first-gone", self.gone(), CLOSED, child=True, name="one")
        self.start()
        self.assertFalse(first.exists())
        self.assertTrue(self.stamp().exists())
        second = self.project("second-gone", self.gone(), CLOSED, child=True, name="two")
        self.start()
        self.assertTrue(second.exists(), "a second session start within the day swept again")
        old(self.stamp(), 2)
        self.start()
        self.assertFalse(second.exists(), "the sweep did not run again after a day")

    def test_a_quiet_start_leaves_no_stamp_where_there_is_no_books_root(self):
        self.start()
        self.assertFalse(self.stamp().exists())

    def test_the_stamp_is_no_project_dir(self):
        self.parent("kid")
        self.project("gone-two", self.gone(), CLOSED, child=True, name="kid")
        self.start()
        self.assertEqual([path.name for path in self.books.iterdir()], ["parent-project"])


if __name__ == "__main__":
    unittest.main()
