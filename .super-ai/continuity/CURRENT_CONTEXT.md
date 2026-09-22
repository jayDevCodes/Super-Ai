# Current Super-Ai Context Snapshot

Snapshot point: main @ ead4f92bfaa32a3478ad28cd92ac6b8ba2b56c4c (step 132 merge checkpoint)
Autonomous checkpoint: steps 32–132 complete; next step 133 — Harden process limits.
Main CI status at the preceding merge checkpoint was green (GitHub Actions run 171); step 132 branch CI run 176 was green on Python 3.11, 3.12, and 3.13.

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
Task → Brain/DAG → Router/Policy → Resource Admission/Lease → Immutable Source Resolution → Secure Staging → Workspace/Output Contracts → Runtime Admission → Sandbox → Container Lifecycle/Attestation → Execution Controller/Session → Verification → Cleanup Fence → Audit/Trace Evidence.

## Durable subsystems
- core/contracts: capability, resources, scheduler, task, workspace, output contracts.
- core/brain: brain orchestration and runtime-step adapter.
- core/router: deterministic capability routing.
- core/planner: task DAG execution.
- core/policy: capability/network/confirmation policy.
- registry: manifest, runtime spec, resolver, catalog.
- core/controlplane: RuntimeSpecGuardian, EngineConfig, deterministic control evidence.
- core/runtime: stager, sandbox, Apple Container executor, preflight, attestation, ownership, telemetry, session, execution controller, pipeline, integration smoke test, admission gate, cleanup guard.
- core/security: environment isolation, capability boundaries, network boundaries, secret scanner, security posture, quotas, evidence, hardening controller, ownership race fence, runtime-intent translation.
- core/supplychain: artifact identity, signatures, provenance, SBOM, dependency locks, revocation, mirrors, trust policy/scoring, registry sync, canonical fingerprints, verification adapters, ArtifactStore, telemetry.
- core/verification: composable fail-closed verifiers.
- core/observability: immutable trace context.
- core/audit: hash-chain audit evidence.
- core/resource_feedback and core/recovery: feedback/retry foundations.
- core/cache: artifact cache foundation.

## Completed checkpoint history
Steps 1-10 established resource-aware scheduling, immutable capability loading/resolution, secure staging, sandbox contracts, execution control, leases/sessions, attestation/telemetry, real-runtime integration, and the initial autonomous engineering framework.
Steps 11-31 established RuntimeSpec contracts, Brain/runtime integration, policy enforcement, trace/audit correlation, secret-safe environment handling, required verification, execution metadata hardening, workspace/output contracts, cancellation, idempotency, and continuity memory.
Steps 32-131 are now merged as the 100-step checkpoint:
- 32-50: runtime-spec hardening, evidence, instrumentation, admission composition, and graduation.
- 51-100: supply-chain identity/evidence, validation, benchmarks, reconciliation, hardening, instrumentation, and graduation.
- 101-131: sandbox security posture, capabilities, syscall/filesystem/network/secret/process controls, quotas, race fencing, evidence, translation, integration, and fail-closed network policy.
- 132: secret-boundary hardening with bounded value-blind environment validation, explicit forbidden-name support, pre-copy validation, and non-secret audit evidence.
- 133: process/open-file hardening with bounded SandboxPolicy limits, Apple Container nproc/nofile flags, pre-start rlimit attestation, contract fingerprinting, and fail-closed tests.

## Key merged commits
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
- Steps 32-131 checkpoint merge: 060a5e5b4570891e8b8a565aa0172d4ef7ba9f49 (PR #47)
- Step 132: ead4f92bfaa32a3478ad28cd92ac6b8ba2b56c4c (PR #48)
- Step 133: b71ad948fb6d10c2da43c385f09b420a884ca139 (PR #49)

## Failure lessons worth retaining
- Old unit tests can become the first regression signal after a contract is tightened; repair existing callers before adding new behavior.
- CI logs must be inspected before assuming a failure is caused by the current feature.
- Step 13 exposed stale tests after policy enforcement.
- Step 20 exposed stale tests after verification became mandatory.
- Step 26 exposed a test-model mismatch around explicit HOME and inherited-environment assertions.
- Steps 32-131 exposed an incorrect test import for the new race-fence classes; CI run 159 caught it and the import was repaired before advancement.
- The export layer was also corrupted once by literal backslash-n characters; CI runs 167/168 caught the syntax regression and both package init files were repaired before the checkpoint proceeded.
- Apple Container behavioral claims cannot be fully proven by Linux-hosted CI; real Apple Silicon smoke tests remain opt-in on an actual compatible macOS host.
- Supply-chain signature verification is intentionally pluggable; the core adapter does not claim to provide a cryptographic implementation itself.

## Validation evidence
- Branch PR #47 completed with 15 commits, 59 changed files, 2282 additions, and 111 deletions before squash merge.
- Final branch CI run 170 passed on Python 3.11, 3.12, and 3.13.
- Main post-merge CI run 171 passed on the merged commit.
- Step 132 PR #48 was merged after run 176 passed on Python 3.11, 3.12, and 3.13.
- Step 132 introduced two CI regressions and repaired both: missing forbidden-name local variable / eager policy validation, then preserved the legacy sensitive-environment error wording.
- Step 133 PR #49 was merged after run 187 passed on Python 3.11, 3.12, and 3.13; main post-merge run 188 also passed.
- Step 133 introduced fixture/API regressions caught by CI and repaired: rlimit fixture completeness, process-limit mismatch fixture preservation, and runtime fingerprint API compatibility.
- New unit tests cover control-plane configuration/specs, supply-chain evidence/policy/sync/verification, security posture/boundaries/evidence, cleanup fencing, admission composition, benchmarks, and telemetry.

## Next-step intent
Step 134 — Harden quotas. Before starting it, audit state, continuity, open PRs, current main CI, older failures, and the existing quota ledger/resource admission contracts. Preserve the same inspect → research → design → implement → test → CI → repair → document → merge → checkpoint loop.

## Never forget
Do not rewrite history to make the project look cleaner. Preserve prior decisions and failures as learning signals. The next agent should build on the existing system instead of starting over.
