#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20+ is required." >&2
  exit 1
fi

node_major="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$node_major" -lt 20 ]; then
  echo "Node.js 20+ is required; found $(node -v)." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required." >&2
  exit 1
fi

tool_dir=".super-ai/browser/tooling"
bin_dir=".super-ai/browser/bin"

# Keep the browser worker inside Super-Ai's ignored local state so the setup
# works without requiring write access to the system-wide npm prefix.
npm install --prefix "$tool_dir" @playwright/cli@latest
mkdir -p "$bin_dir" .super-ai/browser/profile .super-ai/browser/workspace
ln -sf "../tooling/node_modules/.bin/playwright-cli" "$bin_dir/playwright-cli"
"$bin_dir/playwright-cli" install

echo "Browser capability installed."
echo "Use SUPER_AI_PLAYWRIGHT_CLI=$PWD/$bin_dir/playwright-cli when running browser tasks."
echo "Next: log in once with the dedicated profile using docs/browser/GOOGLE_SESSION_SETUP.md"
