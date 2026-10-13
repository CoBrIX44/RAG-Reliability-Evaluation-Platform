export default {
  "apps/web/**/*.{ts,tsx,mjs}": "node node_modules/eslint/bin/eslint.js --config apps/web/eslint.config.mjs --fix --no-warn-ignored --max-warnings 0",
  "*.py": ["uv run ruff check --fix", "uv run ruff format"],
};
