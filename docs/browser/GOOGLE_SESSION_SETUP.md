# Google Web Task Setup

This is the one-time local setup for Super-Ai's browser capability.

## 1. Install the browser worker

Requirements: Node.js 20 or newer.

Run:

```bash
npm install -g @playwright/cli@latest
playwright-cli install
```

The Playwright CLI can target Google Chrome directly and can persist a browser profile across restarts.

## 2. Create a dedicated Google profile

From the repository root:

```bash
mkdir -p .super-ai/browser/profile .super-ai/browser/workspace
playwright-cli -s=super-ai-browser open https://accounts.google.com --browser=chrome --headed --persistent --profile=.super-ai/browser/profile
```

Complete the Google login manually in the opened browser.

Do not put the Google password, recovery codes, cookies, OAuth tokens, or session exports into the repository.

Then close the browser:

```bash
playwright-cli -s=super-ai-browser close
```

## 3. Give a task to Super-Ai

A browser task should explicitly include the sites it may visit. For a Google-hosted application, list only the exact origins required, for example:

```json
{
  "goal": "Perform the approved task on my Google-hosted application",
  "start_url": "https://example.google.com/",
  "allowed_origins": [
    "https://example.google.com",
    "https://accounts.google.com"
  ],
  "session": "super-ai-browser",
  "profile_dir": ".super-ai/browser/profile",
  "workspace_dir": ".super-ai/browser/workspace",
  "headed": true,
  "confirmed": false,
  "actions": [
    {
      "kind": "snapshot"
    },
    {
      "kind": "find_text",
      "target": "Sign in"
    }
  ]
}
```

Use fresh snapshots after page changes. Playwright's accessibility-tree refs are tied to the current page state, so an AI planner should not blindly reuse an old ref after navigation or dynamic DOM changes.

## 4. Consequential steps

Mark a step such as final submission, sending a message, deleting data, purchasing something, or publishing content with:

```json
{
  "kind": "click",
  "target": "@e42",
  "consequential": true
}
```

The browser capability will stop unless `confirmed=true` is supplied by the authorized higher-level workflow.

## Notes for Google

Use a dedicated profile, keep the browser headed while developing, and expect the site to request additional verification sometimes. Super-Ai should pause rather than attempt to bypass a CAPTCHA, 2FA challenge, security warning, or other access-control mechanism.
