const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const requirements = require('./dependency-patches.json');

function verifyDependencyPatches(root = path.resolve(__dirname, '..')) {
  const lock = JSON.parse(readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
  let checked = 0;
  for (const [name, expected] of Object.entries(requirements)) {
    const suffix = `node_modules/${name}`;
    const locations = Object.keys(lock.packages).filter((entry) => entry === suffix || entry.endsWith(`/${suffix}`));
    assert.ok(locations.length > 0, `Security dependency missing from lockfile: ${name}`);
    // Check every locked copy, not only the package Node resolves from the root.
    for (const location of locations) {
      const directory = path.resolve(root, location);
      assert.ok(directory.startsWith(path.resolve(root) + path.sep), 'Invalid lockfile package path');
      const installed = JSON.parse(readFileSync(path.join(directory, 'package.json'), 'utf8'));
      assert.equal(lock.packages[location].version, expected.version, `Review security override for ${location}`);
      assert.equal(installed.version, expected.version, `Installed version mismatch: ${location}`);
      for (const [file, expectedHash] of Object.entries(expected.files)) {
        const actualHash = createHash('sha256').update(readFileSync(path.join(directory, file))).digest('hex');
        assert.equal(actualHash, expectedHash, `Security patch missing or changed: ${location}/${file}; run npm ci`);
      }
      checked++;
    }
  }
  return checked;
}

if (require.main === module) {
  console.log(`Verified security versions and patches for ${verifyDependencyPatches()} installed dependencies.`);
}

module.exports = { verifyDependencyPatches };
