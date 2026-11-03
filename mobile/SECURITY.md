# Mobile Dependency Security

Reviewed: 12 October 2026. Scope: the mobile dependency findings reported during
the reliability review, not a complete mobile penetration test.

## Remediation

| Package | Action | Status |
| --- | --- | --- |
| `decode-uri-component` | Override to official `0.5.0`; adapt `query-string@7.1.3` to its default ESM export | Published fix installed |
| `uuid` | Override to CommonJS-compatible `11.1.1`; test the Xcode identifier generation consumer | Published fix installed |
| `brace-expansion` 1.x | Override ESLint's nested copies to `1.1.21` | Published fixes installed |
| `braces@3.0.3` | Bound parser nesting and recursive compile/expand/stringify traversal; cover string and supplied-AST entry points | Local mitigation; no fixed upstream release available |
| `node-forge@1.4.0` | Enforce nested DigestAlgorithm element count and reject non-NULL or non-empty parameters | Local security backport; no fixed upstream release available |

Expo SDK 57 and the existing React Native/native module versions are retained.
Do not run `npm audit fix --force`: its proposed framework downgrades are not a
compatible remediation. The query decoder update intentionally requires the
small `query-string` interoperability patch; an override without that patch
breaks query parsing.

Sources: [URI decoder advisory](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr),
[UUID advisory](https://github.com/advisories/GHSA-w5hq-g745-h8pq),
[brace-expansion advisory](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr).
The unresolved upstream defects and proposed validation/depth controls are
described in [braces issue 70](https://github.com/micromatch/braces/issues/70) and
[forge issue 1149](https://github.com/digitalbazaar/forge/issues/1149).

## Installation Enforcement

Use Node 22.13+ and install development dependencies when building this mobile
project. `npm ci` runs `patch-package --error-on-fail` and then verifies exact
versions and SHA-256 hashes of the patched source files. Do not skip install
scripts or omit build-time development tools.

`scripts/dependency-patches.json` records the reviewed file hashes. The verifier
checks every matching package location in the lockfile, including nested copies.
Missing files, changed source, unexpected versions and new unpatched copies fail
closed. `npm test` and `npm run check` repeat verification, and CI runs these
security regressions before the existing raw npm audit gate.

Regression tests cover malformed URI input with a subprocess timeout, UUID buffer
bounds and Xcode identifiers, deep brace/parenthesis input and ASTs, valid and
malformed PKCS#1 DigestInfo signatures, and normal certificate verification.
The malformed-signature tests exercise the verifier gap using locally generated
keys; they are not a claim of independently audited cryptographic implementation.

## Audit Status And Release Gate

The original production dependency report contained 30 package findings rooted
in four advisories. Two root advisories are now removed through published fixes.
The raw production report still lists 19 high-severity package findings propagated
from `braces` and `node-forge`. These are two remaining root advisories, not 19
independent application defects. Their affected versions still match the advisory
database despite the local source patches.

The raw npm audit command is unchanged and remains non-zero. No vulnerability
allowlist, severity downgrade, renamed package, fake version or blanket audit
suppression was added. This is **not** a clean-audit or unrestricted-release claim.
The patches mitigate the tested defects but need independent review before being
treated as a production release exception. Native archive, physical-device and
TestFlight acceptance are separate from JavaScript bundle export; no new IPA was
published as part of this change.

## Maintenance

When a fixed official release appears, review its changelog and compatibility,
update the override, remove the corresponding patch, update the verifier manifest
and rerun installation, security tests, lint, typecheck and both platform exports.
Do not simply regenerate a hash to accept an unexplained dependency change. Retain
the behavioral regressions after removing local patches.

```bash
npm ci
npm run check
npm test
npm audit --omit=dev --audit-level=high
npx --no-install expo export --platform ios --platform android --output-dir dist-check
```

The audit command above is currently an expected release blocker, not an ignored
failure. Review upstream releases on every dependency update and before publishing
a native build.

## Verification Evidence

- Clean `npm ci`: passed with automatic application of all three patch files and
  version/hash verification of five installed dependencies.
- `npm run check`: lint and TypeScript passed.
- Unit/regression suite: 25 passed on Node 22 and the local Node 25 runtime.
- iOS and Android production Hermes exports, including external source maps:
  passed. Both maps contain the updated URI decoder and query-string module;
  neither contains `braces` or `node-forge`. This verifies the local exported
  bundles, not the contents of a previously published IPA.
- Final raw audit: production 19 high, all dependencies 21 high; both reports
  have only the two locally patched root advisories (`braces`, `node-forge`).
- Whitespace/error check: passed. No backend data or live deployment was changed.
