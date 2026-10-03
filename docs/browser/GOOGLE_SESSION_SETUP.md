# Google Web Task Setup

Super-Ai now supports both fixed browser action tasks and natural-language browser goals.

## 1. Install the browser worker

Requirements: Node.js 20+.

Run:

```bash
bash scripts/install/browser-agent.sh
```

The script installs the current Playwright CLI and browser runtime.

## 2. Local model lifecycle

The natural-language planner uses local Ollama. Super-Ai now chooses a task-sized Qwen3.5 model from its managed catalog instead of requiring one fixed model to stay installed.

The current catalog includes:
- qwen3.5:0.8b for lightweight extraction/classification;
- qwen3.5:2b-q4_K_M (~1.9 GB) for normal browser work;
- qwen3.5:4b-q4_K_M (~3.4 GB) for more complex or visual work.

All three current Qwen3.5 variants support image input.

When a task starts, the Brain/model manager checks the task's RAM/disk budget and the browser capability footprint. It reuses an already-installed model when present; otherwise it pulls the selected model. At task end it unloads the model from RAM and removes it only when Super-Ai installed it for that task.

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
6. when accessibility context is insufficient, request a screenshot and feed that image to the next planning cycle;
7. continue until deterministic evidence proves the requested post-condition.

This follows the current Playwright guidance to refresh refs after page changes, use find for cheaper targeted lookup, and use screenshots selectively when visual context is needed.

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


## 9. Owner final decision

When a task conflicts with an existing Super-Ai policy, the Brain normally stops. An owner-authenticated decision can explicitly resolve that policy conflict for the current task.

Configure the local verifier:

```bash
python3 scripts/setup_owner_auth.py
```

The code is entered through a hidden prompt. Super-Ai stores only a salted scrypt verifier and never puts the code in browser planner prompts, model context, logs, or task outputs. Current OWASP guidance recommends memory-hard password hashing such as Argon2id or scrypt rather than fast general-purpose hashes.

When the Brain receives a policy conflict, the application may supply `owner_override_code` to `Brain.execute(...)`. Successful verification creates a short-lived, task-scoped authorization proof that can be consumed once. The hash-chain audit records the decision without recording the secret.

This is an owner decision layer over the policy engine, not a general code-execution escape hatch. Deterministic security boundaries remain active.