// node scripts/bench-long-session.mjs [checkout]. For Pi's turn_end preview cost too,
// set BENCH_PI to the absolute path of the installed pi-coding-agent dist/index.js.
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';

const checkout = resolve(process.argv[2] ?? fileURLToPath(new URL('../', import.meta.url)));
const root = mkdtempSync(join(tmpdir(), 'anchorloop-bench-'));
try {
  await replay();
} finally {
  rmSync(root, { recursive: true, force: true });
}

async function replay() {
  const cwd = join(root, 'work');
  const agent = join(root, 'agent');
  Object.assign(process.env, { HOME: root, PI_CODING_AGENT_DIR: agent, ANCHORLOOP_BOOKS_DIR: join(root, 'books') });
  for (const key of Object.keys(process.env)) if (key.startsWith('PI_SUBAGENT_')) delete process.env[key];
  mkdirSync(cwd);
  mkdirSync(join(agent, 'rules'), { recursive: true });
  writeFileSync(join(agent, 'rules/fixture.md'), '---\ncondition: fixture.txt\nscope: tool:read\ninterruptMode: never\n---\nRead the fixture.\n');
  const host = process.env.BENCH_PI ? await import(pathToFileURL(process.env.BENCH_PI)) : undefined;
  registerHooks({ resolve: (name, ctx, next) => name === '@earendil-works/pi-coding-agent'
    ? { url: 'data:text/javascript,export const parseSkillBlock=()=>null', shortCircuit: true } : next(name, ctx) });
  const moduleAt = file => import(pathToFileURL(join(checkout, file)));
  const branch = [], messages = [];
  const append = entry => {
    branch.push({ id: String(branch.length + 1), parentId: branch.at(-1)?.id ?? null, timestamp: new Date(0).toISOString(), ...entry });
    if (entry.type === 'message') messages.push(entry.message);
  };
  const message = (role, text) => ({ role, timestamp: 1, content: [{ type: 'text', text }] });
  for (let i = 0; i < 2048; i++) append({ type: 'message', message: message(i % 2 ? 'assistant' : 'user', `${i} ${'x'.repeat(512)}`) });
  const task = { id: 1, subject: 'Check src/main.ts', status: 'in_progress' };
  append({ type: 'custom', customType: 'rpiv-todo-state', data: { tasks: [task] } });
  const bookModule = await moduleAt('pi/support/book.ts');
  let fullBranchEntries = 0;
  const ctx = { cwd, sessionManager: { getSessionId: () => 'bench', getBranch: () => {
    const path = [];
    for (let entry = branch.at(-1); entry; entry = branch[Number(entry.parentId) - 1]) path.push(entry);
    fullBranchEntries += path.length;
    return path.reverse();
  },
    getLeafId: () => branch.at(-1)?.id, getEntry: id => branch[Number(id) - 1] },
    ui: { notify() {}, setWidget(_key, lines) { widgetWrites++; widget = lines; } }, modelRegistry: { findOfType: () => undefined } };
  const book = bookModule.createBook(ctx);
  const facts = [{ stage: 'kind', kind: 'inline', intent: 'Check the fixture' }, { stage: 'anchor', check: 'npm test' }];
  for (let i = 0; i < 1024; i++) facts.push(i % 4 === 0 ? { stage: 'task', ...task } : i % 2 ? { stage: 'edit', path: 'src/main.ts' } : { stage: 'verify', command: 'npm test', exit: 0 });
  writeFileSync(book.path, facts.map(fact => `- ${JSON.stringify({ ts: new Date(0).toISOString(), ...fact })}\n`).join(''), { flag: 'a' });
  const handlers = new Map(), timings = new Map();
  let widgetWrites = 0, widget, injectedBytes = 0, calls = 0, previews = 0;
  const pi = { on(name, handler) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(handler); },
    registerCommand() {}, registerTool() {}, appendEntry(customType, data) { append({ type: 'custom', customType, data }); },
    sendMessage(msg) { injectedBytes += Buffer.byteLength(msg.content); } };
  for (const file of JSON.parse(readFileSync(join(checkout, 'package.json'))).pi.extensions) (await moduleAt(file)).default(pi);
  function sample(name, ms) { if (!timings.has(name)) timings.set(name, []); timings.get(name).push(ms); }
  // Pi creates a preview before the first boundary handler and after each handler. Use its real
  // projection and message conversion when installed; exclude host work from handler timings.
  function preview() {
    if (!host) return;
    const t = performance.now();
    const header = { type: 'session', version: host.CURRENT_SESSION_VERSION, id: 'bench', timestamp: new Date(0).toISOString(), cwd };
    const manager = host.SessionManager.inMemory(cwd, undefined, [header, ...branch]);
    host.convertToLlm(manager.buildSessionProjection().messages);
    sample('host.turn_end.preview', performance.now() - t); previews++;
  }
  async function emit(name, payload = {}) {
    const hooks = handlers.get(name) ?? [];
    if (name === 'turn_end' && hooks.length) preview();
    let ms = 0;
    for (const fn of hooks) {
      const start = performance.now();
      const result = await fn({ type: name, ...payload }, ctx);
      ms += performance.now() - start;
      if (result?.content) {
        for (const part of result.content.slice(payload.content.length)) injectedBytes += Buffer.byteLength(part.text);
        payload = { ...payload, content: result.content };
      }
      if (name === 'turn_end') preview();
    }
    sample(name, ms);
  }
  await emit('session_start');
  for (let turn = 0; turn < 128; turn++) {
    await emit('turn_start'); await emit('context', { messages }); await emit('message_start');
    const assistant = message('assistant', 'Inspecting the fixture.');
    await emit('message_update', { assistantMessageEvent: { type: 'text_delta', contentIndex: 0, delta: assistant.content[0].text } });
    await emit('message_end', { message: assistant }); append({ type: 'message', message: assistant });
    for (let n = 0; n < 4; n++) {
      const call = { toolName: n === 3 ? 'bash' : 'read', toolCallId: String(++calls), input: n === 3 ? { command: 'pwd' } : { path: 'fixture.txt' } };
      await emit('tool_call', call);
      const result = { ...message('toolResult', 'ok'), toolName: call.toolName, toolCallId: call.toolCallId, isError: false };
      await emit('tool_result', { ...call, ...result }); await emit('message_end', { message: result }); append({ type: 'message', message: result });
    }
    await emit('turn_end');
  }
  assert.deepEqual(widget, ['⚓ inline · act ✓ → verify']);
  assert.equal(injectedBytes, Buffer.byteLength('<rule name="fixture">\nRead the fixture.\n</rule>'));
  assert.equal(calls, 512);
  console.log(`messages=${messages.length} calls=${calls} bookEntries=${facts.length} widgetWrites=${widgetWrites} injectedBytes=${injectedBytes} hostPreviews=${previews} fullBranchEntries=${fullBranchEntries}`);
  for (const [name, times] of timings) {
    times.sort((a, b) => a - b);
    console.log(`${name} n=${times.length} total_ms=${times.reduce((a, b) => a + b, 0).toFixed(2)} p50_ms=${times[times.length >> 1].toFixed(3)} p95_ms=${times[Math.floor(times.length * .95)].toFixed(3)}`);
  }
}
