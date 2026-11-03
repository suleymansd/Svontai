const assert = require('node:assert/strict');
const { generateKeyPairSync } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const braces = require('braces');
const forge = require('node-forge');
const queryString = require('query-string');
const uuid = require('uuid');

test('all locked dependency copies have the reviewed security patches', () => {
  assert.ok(require('../scripts/verify-dependency-patches.cjs').verifyDependencyPatches() >= 5);
});

function withDependencyFixture(run) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'svontai-patch-test-'));
  const lock = { packages: {} };
  try {
    for (const [name, expected] of Object.entries(require('../scripts/dependency-patches.json'))) {
      const location = `node_modules/${name}`;
      const directory = path.join(root, location);
      fs.mkdirSync(directory, { recursive: true });
      fs.writeFileSync(path.join(directory, 'package.json'), JSON.stringify({ version: expected.version }));
      lock.packages[location] = { version: expected.version };
      for (const file of Object.keys(expected.files)) {
        fs.mkdirSync(path.dirname(path.join(directory, file)), { recursive: true });
        fs.copyFileSync(path.join(__dirname, '..', location, file), path.join(directory, file));
      }
    }
    fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify(lock));
    const verify = () => require('../scripts/verify-dependency-patches.cjs').verifyDependencyPatches(root);
    assert.equal(verify(), 5);
    run({ root, lock, verify });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('patch verification fails closed if patched code changes', () => {
  withDependencyFixture(({ root, verify }) => {
    fs.appendFileSync(path.join(root, 'node_modules/node-forge/lib/rsa.js'), '\n');
    assert.throws(verify, /Security patch missing or changed/);
  });
});

test('patch verification does not silently accept a new nested copy', () => {
  withDependencyFixture(({ root, lock, verify }) => {
    const location = 'node_modules/other/node_modules/braces';
    lock.packages[location] = { version: '3.0.3' };
    fs.mkdirSync(path.join(root, location), { recursive: true });
    fs.writeFileSync(path.join(root, location, 'package.json'), JSON.stringify({ version: '3.0.3' }));
    fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify(lock));
    assert.throws(verify, /ENOENT/);
  });
});

test('patch verification requires review of dependency version changes', () => {
  withDependencyFixture(({ root, lock, verify }) => {
    lock.packages['node_modules/node-forge'].version = '1.4.1';
    fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify(lock));
    assert.throws(verify, /Review security override/);
  });
});

test('patched URI decoder preserves query-string and deep-link behavior', () => {
  const parsed = queryString.parse('name=%C4%B0stanbul&tag=a&tag=b&flag&empty=&q=a+b');
  assert.deepEqual({ ...parsed }, {
    empty: '', flag: null, name: '\u0130stanbul', q: 'a b', tag: ['a', 'b'],
  });
  assert.equal(queryString.stringify({ q: 'hello world', id: 'abc' }, { sort: false }), 'q=hello%20world&id=abc');
  assert.equal(queryString.parse('q=%ZZ%41').q, '%ZZA');
});

test('malformed URI decoding completes within a bounded subprocess timeout', () => {
  const result = spawnSync(process.execPath, ['-e', `
    const assert = require('node:assert/strict');
    const query = require('query-string');
    const input = '%A4'.repeat(20000) + '%41';
    const decoded = query.parse('q=' + input).q;
    assert.equal(typeof decoded, 'string');
    assert.ok(decoded.includes('A'));
  `], { cwd: require('node:path').resolve(__dirname, '..'), timeout: 5000, encoding: 'utf8' });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
});

test('uuid rejects undersized buffers without partial writes', () => {
  for (const create of [
    (buffer) => uuid.v3('sample', uuid.v3.DNS, buffer),
    (buffer) => uuid.v5('sample', uuid.v5.DNS, buffer),
    (buffer) => uuid.v6({}, buffer),
  ]) {
    const buffer = new Uint8Array(8).fill(170);
    assert.throws(() => create(buffer), RangeError);
    assert.deepEqual([...buffer], Array(8).fill(170));
  }
});

test('uuid override preserves Xcode project identifier generation', () => {
  const project = require('xcode').project('unused.pbxproj');
  project.hash = { project: { objects: {} } };
  const ids = new Set(Array.from({ length: 100 }, () => project.generateUuid()));
  assert.equal(ids.size, 100);
  for (const id of ids) assert.match(id, /^[A-F0-9]{24}$/);
});

test('braces preserves normal Metro glob operations', () => {
  assert.deepEqual(braces.expand('src/{app,lib}/*.{ts,tsx}'), [
    'src/app/*.ts', 'src/app/*.tsx', 'src/lib/*.ts', 'src/lib/*.tsx',
  ]);
  assert.equal(braces.compile('src/{app,lib}'), 'src/(app|lib)');
  const pattern = 'src/{a,{b,c}}';
  assert.equal(braces.stringify(braces.parse(pattern)), pattern);
  assert.deepEqual(require('micromatch')(['a.ts', 'b.tsx', 'c.js'], '*.{ts,tsx}'), ['a.ts', 'b.tsx']);
});

for (const operation of ['parse', 'compile', 'expand', 'stringify']) {
  test(`braces ${operation} rejects deep brace and parenthesis strings before stack exhaustion`, () => {
    for (const [open, close] of [['{', '}'], ['(', ')']]) {
      for (const suffix of [close.repeat(4000), '']) {
        const pattern = open.repeat(4000) + 'a,b' + suffix;
        assert.throws(() => braces[operation](pattern), {
          name: 'SyntaxError', message: 'Brace pattern exceeds maximum nesting depth of 100',
        });
      }
    }
  });
}

for (const operation of ['compile', 'expand', 'stringify']) {
  test(`braces ${operation} also guards caller-provided ASTs`, () => {
    const root = { type: 'root', nodes: [] };
    let cursor = root;
    for (let depth = 0; depth < 4000; depth++) {
      const child = { type: 'paren', nodes: [], parent: cursor };
      cursor.nodes.push(child);
      cursor = child;
    }
    assert.throws(() => braces[operation](root), {
      name: 'SyntaxError', message: 'Brace pattern exceeds maximum nesting depth of 100',
    });
  });
}

const keys = generateKeyPairSync('rsa', { modulusLength: 2048, publicExponent: 3 });
const privateKey = forge.pki.privateKeyFromPem(keys.privateKey.export({ type: 'pkcs1', format: 'pem' }));
const publicKey = forge.pki.publicKeyFromPem(keys.publicKey.export({ type: 'pkcs1', format: 'pem' }));
const asn1 = forge.asn1;
const node = (type, constructed, value) => asn1.create(asn1.Class.UNIVERSAL, type, constructed, value);

function signature(algorithm, digest, parameters) {
  const info = node(asn1.Type.SEQUENCE, true, [
    node(asn1.Type.SEQUENCE, true, [node(asn1.Type.OID, false, asn1.oidToDer(forge.oids[algorithm]).getBytes()), ...parameters]),
    node(asn1.Type.OCTETSTRING, false, digest),
  ]);
  // Sign a deliberately malformed DigestInfo to exercise the exact verifier gap.
  return privateKey.sign(asn1.toDer(info).getBytes(), 'NONE');
}

test('forge accepts valid SHA signatures and optional NULL parameters', () => {
  for (const algorithm of ['sha1', 'sha256', 'sha384', 'sha512']) {
    const digest = forge.md[algorithm].create().update('svontai-test').digest().getBytes();
    for (const parameters of [[], [node(asn1.Type.NULL, false, '')]]) {
      assert.equal(publicKey.verify(digest, signature(algorithm, digest, parameters)), true);
    }
  }
});

test('forge rejects extra nested DigestAlgorithm elements and invalid parameters', () => {
  const digest = forge.md.sha256.create().update('svontai-test').digest().getBytes();
  for (const parameters of [
    [node(asn1.Type.NULL, false, ''), node(asn1.Type.OCTETSTRING, false, 'garbage')],
    [node(asn1.Type.OCTETSTRING, false, 'garbage')],
    [node(asn1.Type.NULL, false, 'garbage')],
    [node(asn1.Type.NULL, false, ''), node(asn1.Type.NULL, false, '')],
  ]) {
    assert.throws(() => publicKey.verify(digest, signature('sha256', digest, parameters)), /DigestInfo|ASN\.1/);
  }
});

test('forge certificate verification remains usable by Expo signing tools', () => {
  const certificate = forge.pki.createCertificate();
  certificate.publicKey = publicKey;
  certificate.serialNumber = '01';
  certificate.validity.notBefore = new Date('2026-01-01T00:00:00Z');
  certificate.validity.notAfter = new Date('2030-01-01T00:00:00Z');
  const attrs = [{ name: 'commonName', value: 'SvontAI local test' }];
  certificate.setSubject(attrs);
  certificate.setIssuer(attrs);
  certificate.sign(privateKey, forge.md.sha256.create());
  assert.equal(certificate.verify(certificate), true);
});
