const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const source = readFileSync(path.join(__dirname, '../src/lib/api/realtime.tsx'), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const tick = () => new Promise((resolve) => setImmediate(resolve));

function mount({ enabled = true, state = 'active', live = true } = {}) {
  const connections = [];
  const invalidations = [];
  const states = [];
  let cleanup;
  let listener;
  let removed = false;
  const appState = {
    currentState: state,
    addEventListener: (_, callback) => {
      listener = callback;
      return { remove: () => { removed = true; } };
    },
  };
  const mocks = {
    react: {
      createContext: (value) => ({ value }), useContext: (context) => context.value,
      useState: () => [false, (value) => states.push(value)],
      useEffect: (effect) => { cleanup = effect(); },
    },
    'react-native': { AppState: appState },
    '@tanstack/react-query': { useQueryClient: () => ({ invalidateQueries: ({ queryKey }) => invalidations.push(queryKey[0]) }) },
    './client': { openRealtimeStream: async (signal) => {
      let stream;
      const body = new ReadableStream({ start(controller) { stream = controller; } });
      signal.addEventListener('abort', () => stream.close(), { once: true });
      const emit = (payload) => stream.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(payload)}\n\n`));
      connections.push({ signal, emit });
      emit({ type: 'ready', live });
      return { body };
    } },
  };
  const api = {};
  vm.runInNewContext(outputText, {
    exports: api, require: (id) => mocks[id] || require(id),
    setTimeout, clearTimeout, AbortController, TextDecoder,
  });
  api.useMobileRealtime(enabled);
  return { connections, invalidations, states,
    change: (next) => { appState.currentState = next; listener?.(next); },
    cleanup: () => cleanup?.(), removed: () => removed,
  };
}

test('native stream closes in background, reconnects in foreground and cleans up on logout', async () => {
  const app = mount();
  try {
    await tick();
    assert.equal(app.connections.length, 1);
    assert.equal(app.states.at(-1), true);
    app.change('background');
    await tick();
    assert.equal(app.connections[0].signal.aborted, true);
    assert.equal(app.states.at(-1), false);
    app.change('active');
    await tick();
    assert.equal(app.connections.length, 2);
    assert.equal(app.states.at(-1), true);
  } finally { app.cleanup(); }
  await tick();
  assert.equal(app.connections[1].signal.aborted, true);
  assert.equal(app.removed(), true);
});

test('native stream coalesces bursts and never connects without a foreground session', async () => {
  const disabled = mount({ enabled: false });
  const background = mount({ state: 'background' });
  const app = mount();
  try {
    await tick();
    assert.equal(disabled.connections.length, 0);
    assert.equal(background.connections.length, 0);
    for (let i = 0; i < 20; i++) app.connections[0].emit({ type: 'message.created' });
    await new Promise((resolve) => setTimeout(resolve, 300));
    assert.deepEqual(app.invalidations.sort(), ['conversation-messages', 'conversations', 'operator-deliveries']);
  } finally { disabled.cleanup(); background.cleanup(); app.cleanup(); }
});

test('a heartbeat-only backend keeps polling fallback enabled', async () => {
  const app = mount({ live: false });
  try {
    await tick();
    assert.equal(app.states.at(-1), false);
  } finally { app.cleanup(); }
});
