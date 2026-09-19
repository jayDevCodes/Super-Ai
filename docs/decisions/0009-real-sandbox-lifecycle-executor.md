# ADR 0009: Real Sandbox Lifecycle Executor

## Context

Super-Ai previously produced an Apple Container command plan but did not have a production lifecycle adapter. The execution controller therefore could not create, monitor, stop, and delete an isolated container as one owned resource.

Untrusted capability execution must not silently fall back to host subprocess execution.

Current Apple Container documentation exposes explicit lifecycle commands for create, start, stop, kill, delete, and machine-readable inspect/stats. The CLI also supports an explicit `--network none` mode for containers.

## Decision

Add an `AppleContainerExecutor` behind the `SandboxExecutor` protocol.

Each execution follows:

    SandboxPlan
         ↓
    container create --name <unique-id>
         ↓
    verify disabled-network invariant
         ↓
    container start --attach <id>
         ↓
    controller timeout / verification
         ↓
    container stop (graceful)
         ↓
    container kill (fallback)
         ↓
    container delete --force
         ↓
    caller cleanup

The executor uses argv arrays and `shell=False` for every host-side command.

For the default `network=disabled` policy, the plan must contain the exact pair `--network none`. The executor validates that invariant before creating a container.

The root filesystem remains read-only, all Linux capabilities are dropped, the capability source is read-only, the workspace is the only writable bind mount, a non-root user is used by default, and process/CPU/memory limits come from the sandbox policy.

## Execution backend rule

`ExecutionController` no longer silently constructs a host subprocess launcher. A caller must explicitly provide either:

- a trusted local `ProcessLauncher`, or
- a `SandboxExecutor` for isolated capability execution.

This prevents an untrusted capability from accidentally crossing the sandbox boundary through a default fallback.

## Failure handling

- If container creation fails, no start occurs.
- If start fails after creation, the executor attempts immediate forced deletion.
- Timeout asks the container lifecycle to stop, then kill if the attached process still does not exit.
- Final deletion is idempotent from the executor handle's perspective.
- Deletion failures are surfaced as execution cleanup failures.

## Testing

Unit tests use a fake CLI runner so lifecycle behavior is deterministic on Linux CI. Real Apple Container integration remains platform-gated because GitHub Actions for this repository are not the target macOS runtime.

## Consequences

The runtime now has a real isolation boundary suitable for the first untrusted-capability execution path. Resource telemetry via `container stats` remains a follow-up step; the scheduler continues to enforce admission before container creation.

## References

- Apple Container command reference: https://github.com/apple/container/blob/main/docs/command-reference.md
- Apple Container resource usage: https://github.com/apple/container/blob/main/docs/resource-usage.md
- Apple Container network=none support: https://github.com/apple/container/discussions/743
