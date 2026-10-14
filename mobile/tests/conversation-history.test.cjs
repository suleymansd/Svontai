const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const source = readFileSync(path.join(__dirname, '../src/lib/api/conversation-history.ts'), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const api = {};
vm.runInNewContext(outputText, { exports: api });

test('history keeps older pages first and deduplicates overlapping messages', () => {
  const pages = [
    { messages: [{ id: '2', content: 'updated' }, { id: '3' }] },
    { messages: [{ id: '1' }, { id: '2', content: 'old' }] },
  ];
  const result = api.chronologicalMessages(pages);
  assert.equal(JSON.stringify(result.map((m) => m.id)), '["1","2","3"]');
  assert.equal(result[1].content, 'updated');
  assert.equal(pages[0].messages[0].id, '2');
});

test('history tolerates an unloaded first page', () => {
  assert.equal(api.chronologicalMessages().length, 0);
});
