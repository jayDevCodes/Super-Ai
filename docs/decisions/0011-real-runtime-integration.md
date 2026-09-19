# ADR 0011: Real Runtime Integration and Capability Smoke Tests

## Status

Accepted.

## Decision

Super-Ai adds an opt-in real-runtime integration harness for Apple Container on a user-owned Apple Silicon Mac.

The integration boundary is:

`staged capability -> resource lease -> sandbox plan -> container create -> ownership labels -> inspect attestation -> start -> telemetry -> verification -> ownership-checked cleanup -> lease release`

The harness does not make third-party source trusted. It executes only inside the hardened sandbox plan, with the capability mount read-only, workspace writable, the root filesystem read-only, a non-root UID/GID, explicit CPU/RAM/process limits, and disabled networking by default.

## Runtime discovery

`RuntimeProbe` reports:

- `AVAILABLE`: macOS + arm64/aarch64 + container CLI + healthy container system.
- `DEGRADED`: host prerequisites exist but the container service is not ready or its status is malformed.
- `UNAVAILABLE`: unsupported host or missing CLI.

Linux CI continues to run deterministic unit tests. Real Apple Container behavior is opt-in because the Apple Container runtime requires the host platform.

## Ownership and cleanup

Each created container receives:

- a cryptographically random execution UUID embedded in the container ID,
- `com.super-ai.owner=super-ai`,
- `com.super-ai.execution=<execution_uuid>`.

Cleanup re-inspects the container and refuses destructive deletion unless those labels and the exact container ID match the active ownership claim.

This is not a perfect atomic delete guarantee: the current Apple Container API does not expose a compare-and-delete primitive, so a malicious or unrelated actor could still replace a container between inspect and delete. The design therefore minimizes name reuse with high-entropy per-execution IDs and fails closed when ownership cannot be proven.

## Verification

The smoke harness accepts a verifier and records runtime evidence in `ExecutionResult`. Behavioral checks can assert that network access is unavailable, the capability mount is read-only, the workspace is writable, and arbitrary host filesystem paths are not exposed.

## Consequences

This phase proves the integration seam without coupling the core runtime to one specific capability. The next layer can reuse `CapabilitySmokeTest` for real staged GitHub capabilities.
