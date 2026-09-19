# Super-Ai Autonomous 1000-Step Engineering Protocol

## Status

Active standing engineering instruction for the Super-Ai repository.

## Objective

Continue the Super-Ai implementation through the 1000-step roadmap without asking the user for the same implementation prompt again.

## Per-step loop

For every numbered step, execute this exact loop:

1. **Inspect** the current `main` state and the existing implementation.
2. **Research** current authoritative documentation, standards, release notes, security guidance, and relevant primary sources for the step.
3. **Design** the smallest architecture change that fits the existing contracts and the 8 GB RAM / 256 GB storage target.
4. **Implement** the step on an isolated feature branch.
5. **Test** with focused unit/integration/security tests.
6. **Run CI** and inspect failure logs rather than assuming success.
7. **Repair** any regression or test failure before proceeding.
8. **Document** the decision, current limitations, and research basis in `docs/decisions/` or `docs/research/`.
9. **Merge** only after the relevant checks are green.
10. **Advance** the checkpoint in `docs/autonomy/state.json` and continue automatically.

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

Steps 1-10 are complete on `main`.

The next implementation checkpoint starts at **Step 11**.

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

The machine-readable checkpoint is `docs/autonomy/state.json`.
