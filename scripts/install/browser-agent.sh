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

npm install -g @playwright/cli@latest
playwright-cli install

mkdir -p .super-ai/browser/profile .super-ai/browser/workspace

echo "Browser capability installed."
echo "Next: log in once with the dedicated profile using docs/browser/GOOGLE_SESSION_SETUP.md"
