"""The visual-designing measurement script reports overflow, overlap, small targets, and state shifts as numbers."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "visual-designing" / "scripts" / "measure.mjs"

pytestmark = pytest.mark.skipif(
    not (shutil.which("node") and shutil.which("agent-browser")),
    reason="needs node and agent-browser",
)

BAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 390 300" width="390" height="300">
  <style>text{font:16px sans-serif} .btn{fill:#2563eb}</style>
  <defs>
    <g id="chip"><rect id="chip-bg" width="120" height="32" rx="16" fill="#eee"/><text data-in="chip-bg" x="12" y="21">Pending review</text></g>
  </defs>
  <rect id="card" x="20" y="20" width="150" height="60" fill="#f4f4f5"/>
  <text data-in="card" x="30" y="55">A very long product name that overflows</text>
  <use href="#chip" x="20" y="100"/>
  <text x="30" y="125">Overlapping words</text>
  <g data-target="44" transform="translate(20 160)"><rect width="100" height="30" class="btn"/><text x="10" y="20" fill="#fff">Save</text></g>
  <g data-states="Button" transform="translate(20 220)">
    <g data-state="default"><rect id="b1" width="100" height="40" fill="#2563eb"/></g>
    <g data-state="hover" visibility="hidden"><rect width="100" height="40" fill="#1d4ed8" stroke="#000" stroke-width="4"/></g>
    <g data-state="focus" visibility="hidden"><rect width="100" height="40" fill="#2563eb"/><rect data-overlay="" x="-3" y="-3" width="106" height="46" fill="none" stroke="#f90" stroke-width="2"/></g>
  </g>
</svg>
"""

GOOD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 390 300" width="390" height="300">
  <style>text{font:16px sans-serif} .btn{fill:#2563eb}</style>
  <defs>
    <g id="chip"><rect id="chip-bg" width="140" height="32" rx="16" fill="#eee"/><text data-in="chip-bg" x="12" y="21">Pending review</text></g>
  </defs>
  <rect id="card" x="20" y="20" width="350" height="60" fill="#f4f4f5"/>
  <text data-in="card" x="30" y="55">Long product name that fits</text>
  <use href="#chip" x="20" y="100"/>
  <text x="30" y="160">Separate words</text>
  <g data-target="44" transform="translate(20 180)"><rect width="100" height="44" class="btn"/><text x="10" y="28" fill="#fff">Save</text></g>
  <g data-states="Button" transform="translate(20 240)">
    <g data-state="default"><rect width="100" height="40" fill="#2563eb"/></g>
    <g data-state="hover" visibility="hidden"><rect x="2" y="2" width="96" height="36" fill="#1d4ed8" stroke="#000" stroke-width="4"/></g>
    <g data-state="focus" visibility="hidden"><rect width="100" height="40" fill="#2563eb"/><rect data-overlay="" x="-3" y="-3" width="106" height="46" fill="none" stroke="#f90" stroke-width="2"/></g>
  </g>
</svg>
"""


def measure(tmp_path, name, svg):
    frame = tmp_path / name
    frame.write_text(svg)
    return subprocess.run(["node", str(SCRIPT), str(frame)], capture_output=True, text=True, timeout=120)


def test_overflowing_frame_is_red(tmp_path):
    result = measure(tmp_path, "bad.svg", BAD)
    assert result.returncode == 1, result.stdout + result.stderr
    for kind in ("overflow", "overlap", "target", "state"):
        assert kind in result.stdout
    assert "right +144.6" in result.stdout


def test_fixed_frame_is_green(tmp_path):
    result = measure(tmp_path, "good.svg", GOOD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "defects 0" in result.stdout
