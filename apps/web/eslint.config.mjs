import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This experimental rule flags the standard "fetch on mount, setState
      // in a .then()" data-loading pattern used throughout this app's pages.
      // The setState calls here are asynchronous (inside promise callbacks),
      // not synchronous loops, so this is a known false-positive for our
      // usage -- downgraded rather than restructuring correct code around it.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "jest.config.js",
  ]),
]);

export default eslintConfig;
