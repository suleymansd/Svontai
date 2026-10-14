const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

function clientWith(fetch) {
  let storedToken = 'existing-refresh-token';
  let cleared = 0;
  let expired = 0;
  const vault = {
    getRefreshToken: async () => storedToken,
    getOrCreateDeviceId: async () => 'device',
    setRefreshToken: async (value) => { storedToken = value; },
    clearRefreshToken: async () => { storedToken = null; cleared++; },
  };
  const source = readFileSync(path.join(__dirname, '../src/lib/api/client.ts'), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
  const exports = {};
  vm.runInNewContext(outputText, {
    exports, fetch, Headers, Response, AbortController, setTimeout, clearTimeout,
    process: { env: { EXPO_PUBLIC_API_URL: 'https://test.invalid' } },
    require: (name) => {
      if (name === 'expo-constants') return { default: {} };
      if (name.endsWith('session-vault')) return vault;
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  exports.setSessionExpiredHandler(() => expired++);
  return { api: exports, state: () => ({ storedToken, cleared, expired }) };
}

test('offline refresh preserves credentials and recovers on retry', async () => {
  let offline = true;
  const client = clientWith(async () => {
    if (offline) throw new TypeError('Network unavailable');
    return Response.json({ access_token: 'access', refresh_token: 'rotated' });
  });
  await assert.rejects(client.api.restoreMobileSession());
  assert.deepEqual(client.state(), { storedToken: 'existing-refresh-token', cleared: 0, expired: 0 });
  offline = false;
  assert.equal(await client.api.restoreMobileSession(), true);
  assert.equal(client.state().storedToken, 'rotated');
});

for (const status of [429, 500, 503]) {
  test(`HTTP ${status} does not destroy the session`, async () => {
    const client = clientWith(async () => Response.json({ detail: 'Temporary' }, { status }));
    await assert.rejects(client.api.restoreMobileSession());
    assert.equal(client.state().cleared, 0);
    assert.equal(client.state().expired, 0);
  });
}

for (const status of [401, 403]) {
  test(`HTTP ${status} expires a revoked refresh token`, async () => {
    const client = clientWith(async () => Response.json({ detail: 'Revoked' }, { status }));
    await assert.rejects(client.api.restoreMobileSession());
    assert.equal(client.state().cleared, 1);
    assert.equal(client.state().expired, 1);
  });
}
