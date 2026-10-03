# ADR 0051 — First-party Browser Task Agent

## Status

Accepted as an additive capability.

## Decision

Add a first-party `browser.agent` capability backed by the official Playwright CLI rather than importing third-party browser-agent code into the Super-Ai host process.

The capability has four boundaries:

1. **Origin boundary** — every task supplies an explicit HTTPS origin allowlist. Navigation is rejected outside it.
2. **Session boundary** — browser state lives in a dedicated persistent Chrome profile. Credentials are never embedded in task input or source code.
3. **Action boundary** — the planner supplies deterministic actions such as snapshot, find, click, fill, press, and screenshot. Consequential actions require task confirmation.
4. **Filesystem boundary** — screenshots are restricted to a task workspace; browser output is bounded before being returned.

The browser worker is intentionally separate from the existing third-party capability sandbox. This module is first-party control-plane code and does not dynamically execute arbitrary repository code.

## Why Playwright CLI

Current Playwright documentation positions `playwright-cli` specifically for coding-agent browser automation and exposes token-efficient accessibility-tree snapshots plus deterministic interaction commands. It supports Google Chrome and persistent profiles. The project therefore gets a stable browser adapter without adding Python browser dependencies to the control plane.

## Authentication

The user creates and logs into the dedicated profile manually. Super-Ai never stores the password, session cookie, OAuth token, or other credential in Git, task JSON, telemetry, or audit attributes.

## Consequential actions

A click/fill/etc. can be marked `consequential`. A task with `confirmed=false` fails closed before that action. The higher-level Brain and policy engine remain the authoritative route for broader consequential-action decisions.

## Limitations

- Google and other sites can change their UI or introduce anti-automation/verification flows; the agent must not bypass CAPTCHAs or other access controls.
- A separate profile is safer than reusing the user's everyday Chrome profile, but the profile itself still contains sensitive browser state and must remain outside version control.
- Actual browser execution requires Node.js 20+ and a current Playwright CLI installation; unit tests use a fake transport and therefore do not prove live-site behavior.

## Evidence

Playwright's current CLI supports `--browser=chrome`, `--persistent`, custom profiles, accessibility snapshots, and deterministic click/fill/press/screenshot operations. See the official Playwright documentation linked from the project setup guide.
