# Super-Ai

Super-Ai is a modular personal-AI control plane designed for resource-constrained hosts. The repository acts as the durable brain/registry, while untrusted third-party capability code is intended to run only through a least-privilege runtime boundary.

## Current architecture

Task → Brain/DAG → Router/Policy → Resource Admission → Immutable Source Resolution → Staging → Workspace/Output Contracts → Runtime Admission → Sandbox → Execution → Verification → Cleanup → Audit/Telemetry.

The new control-plane layers added after step 31 are additive:
- core/controlplane: runtime-spec hardening and host-footprint configuration;
- core/supplychain: artifact identity, signatures, provenance, SBOM, dependency locks, revocation, mirrors, trust decisions, reconciliation and evidence;
- core/security: capability, syscall, filesystem, network, secret, process, quota and race-fence controls;
- core/runtime/admission.py: composed fail-closed admission;
- core/runtime/cleanup_guard.py: stale-cleanup race barrier.

## Resource target

The default configuration targets approximately 8 GB RAM and 256 GB storage with conservative concurrency and cache limits.

## Safety

Network access is denied by default at the security-posture layer. Third-party source identity is immutable and runtime image digests can be required. Secrets are excluded from the control-plane evidence model.

## Development

The project uses the standard library for the new control-plane modules. The existing GitHub Actions workflow runs the repository unit-test suite on Python 3.11, 3.12 and 3.13.

See docs/autonomy/ for the autonomous engineering protocol and docs/architecture/ for system contracts.
