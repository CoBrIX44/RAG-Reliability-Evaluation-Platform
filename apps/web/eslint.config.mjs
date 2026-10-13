import { defineConfig, globalIgnores } from "eslint/config";
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default defineConfig([
  { files: ["**/*.{ts,tsx}"], extends: [js.configs.recommended, tseslint.configs.recommended], languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  { files: ["**/*.tsx"], extends: [reactHooks.configs.flat.recommended] },
  { files: ["**/*.mjs"], extends: [js.configs.recommended], languageOptions: { globals: globals.node } },
  globalIgnores(["**/.next/**", "**/next-env.d.ts", "**/.venv/**", "**/artifacts/**", "**/data/**", "**/test-results/**", "**/playwright-report/**"]),
]);
