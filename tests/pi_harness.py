"""Loads anchorloop pi extensions with a stub pi API and replays events and tool calls against them.

Every replay runs in a fresh Node process with an isolated HOME and books directory, so a test never
touches the real ~/.pi/agent; the books directory persists across the replays of one test.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PI_DIR = Path(__file__).resolve().parent.parent / "pi"

# Replays steps against the registered handlers and tools and prints what the extensions returned.
HARNESS = """
import { registerHooks } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
// pi provides its own package to extensions; the stub carries the one value export they use.
const PI_STUB = String.raw`export function parseSkillBlock(text) { return null; }`;
registerHooks({
  resolve: (specifier, context, next) =>
    specifier === "@earendil-works/pi-coding-agent"
      ? { url: "data:text/javascript," + encodeURIComponent(PI_STUB), shortCircuit: true }
      : next(specifier, context),
});
const [extensionUrls, cwd, stepsJson, branchJson, classifyJson, sessionId, sessionFile] = process.argv.slice(1);
const handlers = {};
const tools = {};
const branch = JSON.parse(branchJson);
const out = { results: [], classifyCalls: [], questionSets: [], notices: [], appended: [], emitted: [], statuses: [], widgets: [] };
const pi = {
  on: (event, fn) => { (handlers[event] ??= []).push(fn); },
  registerTool: (tool) => { tools[tool.name] = tool; },
  appendEntry: (customType, data) => { out.appended.push({ customType, data }); branch.push({ type: "custom", customType, data }); },
};
for (const url of JSON.parse(extensionUrls)) {
  const { default: register } = await import(url);
  register(pi);
}
const classifyPlan = JSON.parse(classifyJson);
const ctx = {
  cwd,
  ui: {
    notify: (message, level) => out.notices.push({ step: out.results.length, message, level }),
    setStatus: (key, text) => out.statuses.push({ step: out.results.length, key, text: text ?? null }),
    setWidget: (key, lines, options) => out.widgets.push({ step: out.results.length, key, lines: lines ?? null, placement: options?.placement ?? null }),
  },
  sessionManager: { getBranch: () => branch, getSessionId: () => sessionId, getSessionFile: () => sessionFile || undefined },
  modelRegistry: {
    findOfType: (...args) => {
      out.findArgs = args;
      return classifyPlan === "missing" ? undefined : { id: "jev-latest" };
    },
    hasConfiguredAuth: () => classifyPlan !== "no-auth",
    classify: async (_model, context) => {
      out.classifyCalls.push(context.state);
      out.questionSets.push(Object.keys(context.questions));
      if (classifyPlan === "throw") throw new Error("network down");
      const plan = Array.isArray(classifyPlan) ? classifyPlan.shift() : classifyPlan;
      return plan;
    },
  },
};
async function dispatch(event, payload) {
  let merged = null;
  for (const fn of handlers[event] ?? []) {
    const result = await fn(payload, ctx);
    if (!result) continue;
    merged = { ...(merged ?? {}), ...result };
    if (event === "tool_result" && result.content) payload = { ...payload, content: result.content };
  }
  return merged;
}
for (const step of JSON.parse(stepsJson)) {
  try {
    if (step.file) {
      mkdirSync(dirname(resolve(cwd, step.file)), { recursive: true });
      writeFileSync(resolve(cwd, step.file), step.text);
      out.results.push(null);
    } else if (step.branchAdd) {
      branch.push(...step.branchAdd);
      out.results.push(null);
    } else if (step.tool) {
      const result = await tools[step.tool].execute("t1", step.params, undefined, undefined, ctx);
      out.results.push(result ?? null);
      // `emit` also hands the tool's result to the tool_result handlers, as pi does after a tool runs.
      if (step.emit) out.emitted.push(await dispatch("tool_result", { toolName: step.tool, toolCallId: step.emit, input: step.params, content: result.content, details: result.details, isError: false }));
    } else {
      out.results.push((await dispatch(step.event, step.payload ?? {})) ?? null);
    }
  } catch (error) {
    out.results.push({ error: error.message });
  }
}
out.schemas = Object.fromEntries(Object.entries(tools).map(([name, tool]) => [name, { description: tool.description, parameters: tool.parameters }]));
console.log(JSON.stringify(out));
"""


def user_start(prompt: str = "fix the export") -> dict:
    return {"event": "message_end", "payload": {"message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}}


def assistant(text: str) -> dict:
    return {"event": "message_end", "payload": {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}}


def tool_call(tool: str, path: str = "src/app.py", call_id: str = "c1", **extra) -> dict:
    return {"event": "tool_call", "payload": {"toolName": tool, "toolCallId": call_id, "input": {"path": path, "command": "pytest", **extra}}}


def tool_result(tool: str, input: dict, content: str = "ok", call_id: str = "c1", **extra) -> dict:
    payload = {"toolName": tool, "toolCallId": call_id, "input": input, "content": [{"type": "text", "text": content}], "isError": False, **extra}
    return {"event": "tool_result", "payload": payload}


def bash_result(command: str, exit_code: int, output: str = "") -> dict:
    return tool_result("bash", {"command": command}, output, structuredContent={"exit_code": exit_code, "output": output})


def todo_create(subject: str = "write the fix", task_id: int = 1, status: str = "pending", **metadata) -> dict:
    task = {"id": task_id, "subject": subject, "status": status, **({"metadata": metadata} if metadata else {})}
    return tool_result("todo", {"action": "create", "subject": subject}, "created", details={"tasks": [task], "nextId": task_id + 1})


def todo_update(task_id: int, subject: str, status: str, **metadata) -> dict:
    task = {"id": task_id, "subject": subject, "status": status, **({"metadata": metadata} if metadata else {})}
    return tool_result("todo", {"action": "update", "id": task_id, "status": status}, "updated", details={"tasks": [task], "nextId": task_id + 1})


def todo_state(*tasks: dict) -> dict:
    """A branch entry holding the todo list as rpiv-todo persists it."""
    listed = [{"id": i + 1, **task} for i, task in enumerate(tasks)]
    return {"type": "custom", "customType": "rpiv-todo-state", "data": {"tasks": listed, "nextId": len(listed) + 1}}


def write_file(path: str, text: str) -> dict:
    """A step that writes a file under the work directory while the replay runs."""
    return {"file": path, "text": text}


def stage(**params) -> dict:
    return {"tool": "anchorloop_stage", "params": params}


SETTLED = {"event": "agent_settled", "payload": {"aborted": False}}
SETTLE = {"event": "agent_before_settle", "payload": {"outcome": "completed", "entries": [], "continue": False}}


@unittest.skipUnless(shutil.which("node"), "node is required to load the pi extensions")
class ExtensionCase(unittest.TestCase):
    extension = ""
    extensions: tuple[str, ...] = ()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name).resolve()
        self.cwd = root / "work"
        self.cwd.mkdir()
        self.books = root / "books"
        self.home = root / "home"
        self.home.mkdir()
        self.session_file = root / "sessions" / "sess-1.jsonl"
        self.session_file.parent.mkdir()
        self.session_file.write_text("{}\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def env(self, extra: dict | None = None) -> dict:
        # A suite run inside a subagent must not inherit its markers.
        base = {key: value for key, value in os.environ.items() if not key.startswith("PI_SUBAGENT_")}
        base.update({"HOME": str(self.home), "PI_CODING_AGENT_DIR": str(self.home / "agent"), "ANCHORLOOP_BOOKS_DIR": str(self.books)})
        return {**base, **(extra or {})}

    def command(self, steps: list[dict], branch: list | None = None, classify: object = None, extensions: tuple[str, ...] | None = None,
                session: str = "sess-1") -> list[str]:
        names = extensions or self.extensions or (self.extension,)
        return ["node", "--input-type=module", "-e", HARNESS, json.dumps([(PI_DIR / name).as_uri() for name in names]), str(self.cwd),
                json.dumps(steps), json.dumps(branch or []), json.dumps(classify), session, str(self.session_file)]

    def replay(self, steps: list[dict], env: dict | None = None, **kwargs) -> dict:
        proc = subprocess.run(self.command(steps, **kwargs), capture_output=True, text=True, env=self.env(env))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    # --- books ---------------------------------------------------------------------------------

    def book_files(self) -> list[Path]:
        return sorted(self.books.rglob("*.yml")) if self.books.exists() else []

    def book(self, which: Path | None = None) -> tuple[dict, list[dict]]:
        """The header and entries of the only book, read as YAML when PyYAML is present and as JSON lines otherwise."""
        path = which or self.book_files()[0]
        text = path.read_text()
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml:
            data = yaml.safe_load(text)
            return {k: v for k, v in data.items() if k != "entries"}, data["entries"] or []
        header, entries, in_entries = {}, [], False
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            if line == "entries:":
                in_entries = True
            elif in_entries:
                entries.append(json.loads(line[2:]))
            else:
                key, _, value = line.partition(": ")
                header[key] = json.loads(value)
        return header, entries

    def stages(self, which: Path | None = None) -> list[str]:
        """The stages of the entries other than the task records."""
        return [entry["stage"] for entry in self.book(which)[1] if entry["stage"] != "task"]

    def git_repo(self) -> None:
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.cwd), *args], check=True, capture_output=True)
        (self.cwd / "app.py").write_text("print(1)\n")
        subprocess.run(["git", "-C", str(self.cwd), "add", "app.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.cwd), "commit", "-qm", "base"], check=True, capture_output=True)
