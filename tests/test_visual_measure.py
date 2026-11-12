"""The visual-designing measurement script reports overflow, overlap, small targets, and state shifts as numbers."""

import re
import shutil
import signal
import subprocess
import time
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
    assert re.search(r"overflow .*right \+\d", result.stdout), result.stdout


def test_fixed_frame_is_green(tmp_path):
    result = measure(tmp_path, "good.svg", GOOD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "defects 0" in result.stdout


def frame(body, defs="", style=""):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 400 300" width="400" height="300">'
        f"<style>text{{font:14px sans-serif}}{style}</style><defs>{defs}</defs>{body}</svg>"
    )


def test_symbol_children_are_measured(tmp_path):
    svg = frame(
        '<use href="#s" x="10" y="10"/>',
        '<symbol id="s"><rect id="r" width="60" height="20"/><text data-in="r" x="2" y="15">A very long overflowing label</text></symbol>',
    )
    result = measure(tmp_path, "symbol.svg", svg)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "overflow" in result.stdout


def test_data_target_on_use_is_checked(tmp_path):
    svg = frame('<use href="#b" data-target="44" x="10" y="10"/>', '<rect id="b" width="20" height="20"/>')
    result = measure(tmp_path, "target.svg", svg)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "target" in result.stdout.split("defects", 1)[1]


def test_data_state_on_use_is_checked(tmp_path):
    svg = frame(
        '<g data-states="B"><use href="#a" data-state="default"/><use href="#c" data-state="hover" visibility="hidden"/></g>',
        '<rect id="a" width="100" height="40"/><rect id="c" width="80" height="40"/>',
    )
    result = measure(tmp_path, "state.svg", svg)
    assert result.returncode == 1, result.stdout + result.stderr
    assert re.search(r"^\s+state ", result.stdout, re.M), result.stdout


def test_use_id_is_a_container(tmp_path):
    svg = frame(
        '<use id="u1" href="#bg" x="10" y="10"/><text data-in="u1" x="14" y="30">Hi</text>',
        '<rect id="bg" width="100" height="40"/>',
    )
    result = measure(tmp_path, "useid.svg", svg)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "defects 0" in result.stdout


def test_data_in_resolves_through_nested_use(tmp_path):
    svg = frame(
        '<use href="#outer" x="100" y="100"/>',
        '<g id="outer"><rect id="card" width="80" height="30"/><use href="#label"/></g>'
        '<g id="label"><text data-in="card" x="5" y="20">Hi</text></g>',
    )
    result = measure(tmp_path, "nested.svg", svg)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "defects 0" in result.stdout


def test_id_selector_css_reaches_placed_copies(tmp_path):
    svg = frame(
        '<use href="#btn" x="10" y="10"/>',
        '<g id="btn"><g data-states="B"><g data-state="a"><rect width="100" height="40"/></g>'
        '<g data-state="b" visibility="hidden"><rect id="hv" width="100" height="40"/></g></g></g>',
        "#hv{stroke:#000;stroke-width:8}",
    )
    result = measure(tmp_path, "idcss.svg", svg)
    assert result.returncode == 1, result.stdout + result.stderr
    assert re.search(r"^\s+state ", result.stdout, re.M), result.stdout


@pytest.mark.parametrize("extra", [["--tol"], ["--tol", "abc"], ["--min-target", ""], ["--bogus", "1"]])
def test_bad_option_exits_2(tmp_path, extra):
    path = tmp_path / "good.svg"
    path.write_text(GOOD)
    result = subprocess.run(["node", str(SCRIPT), *extra, str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "usage" in result.stderr


def sessions():
    out = subprocess.run(["agent-browser", "session", "list"], capture_output=True, text=True, timeout=30).stdout
    return set(re.findall(r"measure-\d+", out))


def test_sigterm_closes_its_session(tmp_path):
    path = tmp_path / "good.svg"
    path.write_text(GOOD)
    proc = subprocess.Popen(["node", str(SCRIPT), *[str(path)] * 40], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    name = f"measure-{proc.pid}"
    try:
        deadline = time.time() + 60
        while name not in sessions():
            assert proc.poll() is None and time.time() < deadline, "the run ended before its session appeared"
            time.sleep(0.2)
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)
        deadline = time.time() + 20
        while name in sessions() and time.time() < deadline:
            time.sleep(0.5)
        assert name not in sessions()
    finally:
        if proc.poll() is None:
            proc.kill()
        subprocess.run(["agent-browser", "--session", name, "close"], capture_output=True, timeout=30)
