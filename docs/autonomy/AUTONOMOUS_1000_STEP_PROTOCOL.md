# Super-Ai Autonomous 1000-Step Engineering Protocol

## Status

Active standing engineering instruction for the Super-Ai repository.

## Objective

Continue the Super-Ai implementation through the 1000-step roadmap without asking the user for the same implementation prompt again.

## Mandatory pre-step gate

Before starting every next numbered step, the workflow must first:

0. **Audit pending work.** Check for any open pull request belonging to this autonomous Super-Ai program. Inspect its state, diff, review status, and CI.
1. **Audit CI history.** Check the latest status for main and inspect recent workflow runs for the current program branch/PR. Treat failures from older test cases as actionable until their cause is known and the current branch is green.
2. **Repair before advancing.** If any existing test case or CI job is failing, stop new feature work, research the failure using the relevant logs and current authoritative guidance, implement the smallest repair, and rerun focused tests plus CI.
3. **Close the PR gate.** Do not begin the next step while an autonomous program PR remains open. A ready-and-green PR should be merged; a failing PR must be repaired until green before merge.
4. **Re-check after merge.** After merging a pending PR, verify main is green again before beginning the next numbered step.

This gate is part of the standing workflow and applies even when the previous step looked complete.

## Per-step loop

For every numbered step, execute this exact loop:

1. **Inspect** the current main state and the existing implementation.
2. **Research** current authoritative documentation, standards, release notes, security guidance, and relevant primary sources for the step.
3. **Design** the smallest architecture change that fits the existing contracts and the 8 GB RAM / 256 GB storage target.
4. **Implement** the step on an isolated feature branch.
5. **Test** with focused unit/integration/security tests.
6. **Run CI** and inspect failure logs rather than assuming success.
7. **Repair** any regression or test failure before proceeding.
8. **Document** the decision, current limitations, and research basis in docs/decisions/ or docs/research/.
9. **Merge** only after the relevant checks are green.
10. **Advance** the checkpoint in docs/autonomy/state.json and continue automatically.

## User interaction rule

Routine implementation, testing, documentation, branch creation, pull requests, merges, and non-destructive refactors do not require another user prompt.

Ask for user input only when the next step requires a credential/secret, a real-world consequential action, destructive deletion outside the repository's controlled workspace, or an irreversible choice whose requirements are genuinely ambiguous.

## Safety invariants

- Third-party code is untrusted by default.
- Never import/execute downloaded repository code in the host process.
- Immutable Git commits and verified artifact digests remain mandatory.
- Sandbox execution remains least-privilege and fail-closed.
- Network access is opt-in and policy-gated.
- Consequential external actions require explicit confirmation.
- Resource limits are enforced before execution; telemetry is advisory until explicitly accepted.
- Verification is required for important outputs.
- Cleanup must be ownership-checked.
- Secrets never enter source control, audit attributes, prompts, test fixtures, or telemetry.
- No autonomous self-modification of security/policy controls without tests and an auditable change.
- Prefer deterministic code before model-based behavior.
- Benchmark resource use on the target-class hardware before increasing model/runtime weight.

## Current checkpoint

Steps 1-10 are complete on main.

The next implementation checkpoint starts at Step 11.

## Definition of done for the 1000-step program

A step is complete only when its code (when applicable), tests, documentation, and validation state are committed and the corresponding checkpoint is recorded.

The roadmap is a plan, not proof of implementation. A step becomes green only after the per-step loop completes.

## Recovery rule

If a step fails validation, do not skip it silently. Repair the step, record the failure and fix, then continue from the same step.

## Research rule

Use current primary/official sources whenever a step depends on changing APIs, model runtimes, browser standards, security practices, package versions, platform behavior, or service capabilities. Record source dates and version assumptions in the step's research note.

## Performance rule

Every runtime or model-related step must preserve the principle:

**reliable work per unit of resource > raw model size.**

## Autonomy checkpoint file

The machine-readable checkpoint is docs/autonomy/state.json.

## Persistent agent continuity gate

Every agent/session working on this program must read `.super-ai/continuity/README.md`, `.super-ai/continuity/CURRENT_CONTEXT.md`, and `.super-ai/continuity/AGENT_HANDOFF.md` before starting a step.

At the end of every validated step, the agent must update `CURRENT_CONTEXT.md` and append a compact entry to `JOURNAL.md` before advancing `docs/autonomy/state.json`.

The continuity layer preserves structured engineering facts, decision rationale, research assumptions, test evidence, failure lessons, and handoff state. It must never contain secrets, credentials, private user data, or private chain-of-thought.

The repository is the durable handoff surface: a new agent must be able to resume from source code, tests, ADRs, roadmap/state, and the continuity folder without relying on an unavailable prior chat session.
