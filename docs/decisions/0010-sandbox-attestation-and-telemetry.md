# ADR 0010: Sandbox Runtime Attestation and Telemetry

## Context

Super-Ai now creates an Apple Container and has a scheduler/resource lease around execution. A command plan alone is not sufficient evidence that the created container actually matches the intended security boundary.

Apple Container exposes machine-readable `container inspect` output containing container configuration, resource allocation, mounts, image descriptor, process user, capabilities, and network attachments. It also exposes machine-readable `container stats` with memory, CPU counters, network I/O, block I/O, and process count.

## Decision

Before an untrusted container starts:

1. Check that the Apple Container system reports healthy.
2. Inspect the requested image and resolve its current immutable digest.
3. Create the named container.
4. Inspect the created container.
5. Fail closed unless the observed configuration matches the expected policy.
6. Start the container only after attestation passes.

For the default sandbox policy, attestation verifies:

- exact container ID;
- image reference and digest;
- requested CPU count;
- requested memory allocation;
- read-only root filesystem;
- ALL Linux capabilities dropped;
- explicit non-root execution user;
- exactly the capability and workspace mounts;
- capability mount read-only;
- workspace mount writable;
- zero network attachments when network is disabled.

The image digest resolved during preflight becomes the expected digest for post-create attestation when the plan did not already provide one. If a moving image tag changes between preflight and create, attestation detects the mismatch and aborts before start.

Runtime telemetry uses `container stats --format json --no-stream`. Telemetry is advisory and must never block, alter, or determine workload success. CPU percentage is calculated from the cumulative `cpuUsageUsec` counter only when at least two samples exist.

## Resource-aware behavior

Telemetry is bounded to one in-memory sample record per successful sampling interval and is retained only with the execution result. The scheduler remains authoritative for admission; observed telemetry is for diagnostics, benchmarking, future adaptive scheduling, and regression detection.

Disk reclamation remains separate from per-task execution cleanup. Do not run global prune operations after every task.

## Platform testing

Linux CI uses fake command runners for deterministic unit tests. Actual Apple Container integration is intentionally platform-gated because the repository's general CI matrix is not a macOS Apple Silicon runtime.

## Consequences

The runtime changes from:

    plan → create → start

to:

    preflight → create → inspect/attest → start → telemetry → stop/kill → delete

This strengthens the trust boundary without coupling the rest of Super-Ai to Apple Container's implementation details.

## References

- Apple Container command reference: https://github.com/apple/container/blob/main/docs/command-reference.md
- Apple Container inspection: https://github.com/apple/container/blob/main/docs/container-inspection.md
- Apple Container resource usage: https://github.com/apple/container/blob/main/docs/resource-usage.md
