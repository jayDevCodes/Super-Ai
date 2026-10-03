# Google Web Task Setup

Super-Ai now supports both fixed browser action tasks and natural-language browser goals.

## 1. Install the browser worker

Requirements: Node.js 20+.

Run:

```bash
bash scripts/install/browser-agent.sh
```

The script installs the current Playwright CLI and browser runtime.

## 2. Install a local planning model

The natural-language planner uses Ollama locally. For an approximately 8 GB machine, a small Qwen3.5 model is the intended starting point.

Recommended planning model:

```bash
ollama pull qwen3.5:4b-q4_K_M
```

The current Ollama registry lists this model at about 3.4 GB. A smaller option is:

```bash
ollama pull qwen3.5:2b-q4_K_M
```

Set the choice with:

```bash
export SUPER_AI_BROWSER_MODEL=qwen3.5:4b-q4_K_M
```

Make sure Ollama is running locally before starting a natural-language browser goal.

## 3. Create a dedicated Google profile

From the repository root:

```bash
mkdir -p .super-ai/browser/profile .super-ai/browser/workspace

playwright-cli -s=super-ai-browser open https://accounts.google.com   --browser=chrome   --headed   --persistent   --profile=.super-ai/browser/profile
```

Complete the Google login manually in the opened browser.

Do not put passwords, recovery codes, cookies, OAuth tokens, or storage-state files into the repository.

Then:

```bash
playwright-cli -s=super-ai-browser close
```

## 4. Give Super-Ai a natural-language goal

Example:

```bash
python3 scripts/run_browser_goal.py \
  "Open my Google-hosted application and inspect what I need to do next" \
  --start-url https://example.google.com/ \
  --allowed-origin https://example.google.com \
  --allowed-origin https://accounts.google.com
```

Super-Ai will repeatedly:

1. inspect the current URL and accessibility snapshot;
2. ask the planner for one next action;
3. validate the action;
4. execute it through Playwright;
5. inspect again with fresh refs;
6. continue until the planner supplies grounded completion evidence.

## 5. Consequential actions

For a task such as sending, submitting, publishing, deleting, purchasing, paying, booking, ordering, or transferring, the agent stops and shows a confirmation prompt.

You can pre-approve the run with:

```bash
python3 scripts/run_browser_goal.py \
  "Submit the prepared form" \
  --start-url https://example.google.com/ \
  --allowed-origin https://example.google.com \
  --confirm
```

Use `--confirm` only when you intentionally authorize the external action.

## 6. Brain integration

For a browser-only Brain task, use `BrowserGoalStepRunner` as the Brain's StepRunner. Supply:

```text
__browser_start_url
__browser_allowed_origins
__browser_confirmed
```

The Brain continues to own routing, task constraints, audit, and confirmation policy; the browser runner owns the observe/plan/execute/verify loop.

## 7. Important safety behavior

The planner treats webpage content as untrusted data and must ignore instructions embedded in pages that try to override Super-Ai's rules, expose secrets, disable safeguards, or navigate outside the explicit origin allowlist.

Super-Ai must stop for CAPTCHA, 2FA, security warnings, unexpected origins, missing evidence, or ambiguous consequential actions. It must not attempt to bypass those controls.

## 8. Troubleshooting

Check Playwright:

```bash
playwright-cli --version
```

Check the named session:

```bash
playwright-cli list
```

Check Ollama:

```bash
ollama list
```

A planner error generally means Ollama is unavailable or the selected model is not installed.

Browser-state files under `.super-ai/browser/` and `.playwright-cli/` are intentionally ignored by Git.
