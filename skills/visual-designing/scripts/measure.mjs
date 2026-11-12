#!/usr/bin/env node
// Measure SVG frames in a headless browser (agent-browser) and print defects as numbers.
// Usage: node measure.mjs [--min-target 44] [--tol 0.5] frame.svg [frame.svg ...]
// Exit code: 0 clean, 1 defects found, 2 the measurement could not run.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const opts = { minTarget: 44, tol: 0.5 };
const files = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--min-target") opts.minTarget = Number(args[++i]);
  else if (args[i] === "--tol") opts.tol = Number(args[++i]);
  else files.push(args[i]);
}
if (!files.length) {
  console.error("usage: node measure.mjs [--min-target 44] [--tol 0.5] frame.svg ...");
  process.exit(2);
}

const session = `measure-${process.pid}`;
const ab = (cmdArgs, input) =>
  execFileSync("agent-browser", ["--session", session, ...cmdArgs], { input, encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] });
const script = `window.__measureOpts = ${JSON.stringify(opts)};\n` +
  readFileSync(new URL("./measure.js", import.meta.url), "utf8");

let total = 0;
try {
  for (const file of files) {
    ab(["open", pathToFileURL(resolve(file)).href]);
    // eval prints the returned object as JSON; a string result arrives JSON-encoded once more.
    let out = JSON.parse(ab(["eval", "--stdin"], script));
    if (typeof out === "string") out = JSON.parse(out);
    total += out.findings.length;
    console.log(`${basename(file)}  canvas ${out.canvas}  texts ${out.texts}  targets ${out.targets}  state sheets ${out.states}  defects ${out.findings.length}`);
    for (const f of out.findings) console.log(`  ${f.kind.padEnd(9)} ${f.msg}`);
  }
} catch (e) {
  console.error(`measurement could not run: ${(e.stderr || e.message).toString().trim()}`);
  process.exitCode = 2;
  total = -1;
} finally {
  try { ab(["close"]); } catch {}
}
if (total > 0) process.exitCode = 1;
