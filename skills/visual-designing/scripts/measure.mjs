#!/usr/bin/env node
// Measure SVG frames in a headless browser (agent-browser) and print defects as numbers.
// Usage: node measure.mjs [--min-target 44] [--tol 0.5] frame.svg [frame.svg ...]
// Exit code: 0 clean, 1 defects found, 2 the measurement could not run.
import { execFile, execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, basename } from "node:path";
import { pathToFileURL } from "node:url";

const USAGE = "usage: node measure.mjs [--min-target 44] [--tol 0.5] [--timeout 60] frame.svg ...";
const fail = (msg) => { console.error(`${msg}\n${USAGE}`); process.exit(2); };

const args = process.argv.slice(2);
const opts = { minTarget: 44, tol: 0.5 };
let timeoutSec = 60;
const files = [];
const numberAfter = (i, flag) => {
  const v = args[i + 1];
  const n = v === undefined || v.trim() === "" ? NaN : Number(v);
  if (!Number.isFinite(n) || n < 0) fail(`${flag} needs a non-negative number, got ${v === undefined ? "nothing" : `"${v}"`}`);
  return n;
};
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--min-target") opts.minTarget = numberAfter(i++, "--min-target");
  else if (args[i] === "--tol") opts.tol = numberAfter(i++, "--tol");
  else if (args[i] === "--timeout") timeoutSec = numberAfter(i++, "--timeout");
  else if (args[i].startsWith("--")) fail(`unknown option ${args[i]}`);
  else files.push(args[i]);
}
if (!files.length) fail("no frame given");

// The run uses its own empty config and no AGENT_BROWSER_* settings, so ambient auto-connect, cdp,
// profile, or headed settings cannot point it at the user's own browser.
const configDir = mkdtempSync(join(tmpdir(), "measure-cfg-"));
const configPath = join(configDir, "config.json");
writeFileSync(configPath, "{}");
const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith("AGENT_BROWSER_")));
const session = `measure-${process.pid}`;
const base = ["--config", configPath, "--session", session, "--headed", "false", "--idle-timeout", "30s"];
const ab = (cmdArgs, input) => new Promise((res, rej) => {
  const child = execFile("agent-browser", [...base, ...cmdArgs],
    { encoding: "utf8", env, timeout: timeoutSec * 1000, killSignal: "SIGKILL", maxBuffer: 64 * 1024 * 1024 },
    (err, stdout, stderr) => { if (err) { err.stderr = stderr || err.stderr; rej(err); } else res(stdout); });
  if (input !== undefined) child.stdin.end(input); else child.stdin.end();
});

// Only a session this run started is closed, by its own name.
let started = false;
let closed = false;
const cleanup = () => {
  if (started && !closed) {
    closed = true;
    try { execFileSync("agent-browser", [...base, "close"], { env, stdio: "ignore", timeout: 15000 }); } catch {}
  }
  try { rmSync(configDir, { recursive: true, force: true }); } catch {}
};
for (const [sig, code] of [["SIGINT", 130], ["SIGTERM", 143], ["SIGHUP", 129]]) {
  process.on(sig, () => { cleanup(); process.exit(code); });
}
process.on("exit", cleanup);

const script = `window.__measureOpts = ${JSON.stringify(opts)};\n` +
  readFileSync(new URL("./measure.js", import.meta.url), "utf8");

let total = 0;
try {
  for (const file of files) {
    started = true;
    await ab(["open", pathToFileURL(resolve(file)).href]);
    // eval prints the returned object as JSON; a string result arrives JSON-encoded once more.
    let out = JSON.parse(await ab(["eval", "--stdin"], script));
    if (typeof out === "string") out = JSON.parse(out);
    total += out.findings.length;
    console.log(`${basename(file)}  canvas ${out.canvas}  texts ${out.texts}  targets ${out.targets}  state sheets ${out.states}  defects ${out.findings.length}`);
    for (const f of out.findings) console.log(`  ${f.kind.padEnd(9)} ${f.msg}`);
  }
} catch (e) {
  console.error(`measurement could not run: ${(e.killed ? `timed out after ${timeoutSec}s` : (e.stderr || e.message)).toString().trim()}`);
  process.exitCode = 2;
  total = -1;
}
cleanup();
if (total > 0) process.exitCode = 1;
