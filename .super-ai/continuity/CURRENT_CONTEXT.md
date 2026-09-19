# Current Super-Ai Context Snapshot

Snapshot point: main @ 628651d80357e6d98b2e422492a5d36a5cdc8474
Autonomous checkpoint: step 31 complete; next step 32 — Harden runtime specs.
Main CI status at the latest recorded checkpoint: green.

## Mission
Build a modular personal AI that can decompose large tasks, select deterministic tools/specialized capabilities, execute untrusted third-party capability code only inside a least-privilege sandbox, verify outputs, clean up safely, and stay usable on approximately 8 GB RAM / 256 GB storage.

## Core architectural principles
1. The Git repository is the durable brain/skill warehouse and registry.
2. Third-party GitHub capabilities are untrusted by default and must never be imported/executed in the host process.
3. Prefer deterministic tools before model-based behavior.
4. Use resource-aware admission and temporary capability loading instead of keeping every model/tool resident.
5. Immutable source pins and image digests are mandatory for trusted execution.
6. Sandbox execution is fail-closed: least privilege, non-root, read-only root filesystem, bounded CPU/RAM/processes, explicit network policy.
7. Network is disabled by default and must be policy-gated for access.
8. Verification is required for important outputs.
9. Cleanup is ownership-checked and must not delete a replacement or unrelated container.
10. Secrets must never enter source control, prompts, audit attributes, fixtures, or telemetry.
11. Reliable work per unit of resource is preferred over raw model size.

## Runtime pipeline
Task → Brain/DAG → Router/Policy → Resource Admission/Lease → Immutable source resolver → Secure stager → Workspace/Output contracts → Sandbox plan → Container lifecycle/attestation → Execution controller/session → Verification → Cleanup → Audit/trace evidence.

## Durable subsystems already present
- core/contracts: capability, resources, scheduler, task, workspace contracts.
- core/brain: brain orchestration and runtime-step adapter.
- core/router: deterministic capability routing.
- core/planner: task DAG execution.
- core/policy: capability/network/confirmation policy.
- registry: manifest, runtime spec, resolver, catalog.
- core/runtime: stager, sandbox, Apple Container executor, preflight, attestation, ownership, telemetry, session, execution controller, pipeline, integration smoke test.
- core/security: secret-safe environment construction.
- core/verification: composable fail-closed verifiers.
- core/observability: immutable trace context.
- core/audit: hash-chain audit evidence.
- core/resource_feedback and core/recovery: feedback/retry foundations.
- core/cache: artifact cache foundation.

## Important step history
Steps 1-10 established resource-aware scheduling, immutable capability loading/resolution, secure staging, sandbox contracts, execution control, leases/sessions, attestation/telemetry, real-runtime integration, and the initial autonomous engineering framework.
Step 11: explicit RuntimeSpec contract.
Step 12: Brain → Runtime adapter.
Step 13: runtime policy enforcement.
Step 14: immutable trace context.
Step 15: Brain trace/audit correlation.
Step 16: secret-safe sandbox environment.
Step 17: composite verification.
Step 18: trusted runtime audit events.
Step 19: runtime trace propagation.
Step 20: verification-required capability enforcement.
Step 21: bounded execution metadata projection and benchmark.
Step 22: RuntimeSpec validation benchmark.
Step 23: ownership benchmark.
Step 24: lifecycle benchmark.
Step 25: image identity benchmark.
Step 26: environment isolation integrated at the container boundary.
Step 27: workspace contracts integrated from runtime request through sandbox plan/executor.
Step 28: output contracts integrated and bounded filesystem evidence attached to execution results.
Step 29: cancellation propagated through brain context → runtime request → session/controller.
Step 30: keyed execution idempotency, semantic fingerprinting, replay bounds/conflict handling, and brain workspace stabilization.
Step 31: hardened execution metadata with bounded/sanitized/versioned control-plane projection and strict digest/numeric handling.

## Key merged commits for continuity
- Step 11: f5afa8339fbe11fa73c7b0829d9c59e2b31fa723
- Step 12: c3eb8192b93867b809b8044130b7d2158f17c469
- Step 13: bd64e4391425c74258b3d62bec73b218250e1210
- Step 14: f7fac4619484d88e876bba1d6df8f38915e4f6b1
- Step 15: 90b3c2079c650b4488f9e731b52c99797e7d4f97
- Step 16: 5804a42adc38908619654cc49288a380cf8499d8
- Step 17: 9b76340a43f18c6ec3677f5d4f0468aea35b4d37
- Step 18: cda06ea2cfc0cd92c5937e637a0bf8d3786210f6
- Step 19: 27f438a3a39a3afe63cdbeb3563e669fe2275f7d
- Step 20: 85ef4c39f8b8bcc85127066ec193c26c60537436
- Step 21: 5ccf89d77c74a1c8cc74d51679b67ad1d2b50f0c
- Step 22: b2fecb5ecd7b4d700637de0d5e948265f92a364f
- Step 23: f941aaef4338a83e778cb50d51f9da1ddad4dcc2
- Step 24: 4a564c94cf2eac3357ecea6d5cf3f3d9c889ca2a
- Step 25: 5d8e975c89fefe766b0aec7c1b1f8ca3991b6767
- Step 26: 61c1677de5944ecf6a996c01417b5ae54c5a86d8
- Step 27: 32b39166fd06901cf959b700a6beb0f37a7828ec
- Step 28: 454e3050f581b3a4d0be6acf3b24c421d5fb5d48
- Step 29: 6fb190d9aa63a23f6d288643b960dae345a851e0
- Step 30: 0a7620e605eeb8a4fc3909ce8bcb0a2b382a19b7
- Step 31: 628651d80357e6d98b2e422492a5d36a5cdc8474

## Failure lessons worth retaining
- Old unit tests can become the first regression signal after a contract is tightened; repair existing callers before adding new behavior.
- CI logs must be inspected before assuming a failure is caused by the current feature.
- Step 13 exposed stale tests after policy enforcement.
- Step 20 exposed stale tests after verification became mandatory.
- Step 26 initially failed because a test explicitly supplied HOME while also asserting HOME was absent from inherited environment; the test was corrected to model the actual allowlist boundary.
- Apple Container behavioral claims cannot be fully proven by Linux-hosted CI; real Apple Silicon smoke tests remain opt-in on an actual compatible macOS host.

## Current known code-quality note
core/runtime/execution.py currently contains one _with_runtime_data definition on main. A prior snapshot had a duplicate definition; this was checked again while preparing this handoff.

## Next-step intent
Step 32 is to harden RuntimeSpec validation without breaking the existing immutable registry/runtime contracts. Before starting it, audit open PRs, recent CI, current main, and this continuity folder. Research current authoritative runtime/image reference rules, implement the smallest compatible hardening, test, repair, document, merge, and checkpoint.

## Never forget
Do not rewrite history to make the project look cleaner. Preserve prior decisions and failures as learning signals. The next agent should build on the existing system instead of starting over.