import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      'react/no-unescaped-entities': 'off',
      '@next/next/no-html-link-for-pages': 'off',
      // These compiler-oriented rules were introduced after this codebase was
      // built. They are migrated incrementally while correctness rules remain on.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
    },
  },
  globalIgnores([
    '.next/**',
    'node_modules/**',
    'playwright-report/**',
    'test-results/**',
    'next-env.d.ts',
  ]),
])
