# ADR 0037: Workspace Contract Integration

## Status

Accepted — step 27.

## Decision

Introduce an immutable WorkspaceContract at the runtime contract layer and carry it through every sandbox plan.

The contract establishes three filesystem roles for one disposable execution:

- root: the task-owned host directory allowed for writable workspace output.
- source_path: the staged third-party capability, which must remain read-only.
- output_path: a strict child of root, writable by the capability and never overlapping the source.

The contract rejects symlinked roots/sources, output paths that escape the workspace root after resolution, output/source overlap, and attempts to make the untrusted capability source writable.

CapabilityExecutionRequest now carries an explicit workspace_root. The runtime validates and creates the output directory through the workspace contract before producing the sandbox plan. The sandbox planner validates the contract, and the executor re-validates the plan contract immediately before launch.

This closes a boundary in which a caller could otherwise provide an arbitrary host output directory that was only treated as a plain path.

## Runtime mapping

The Apple Container backend mounts capability source to /capability as read-only and workspace output to /workspace as read-write, while keeping the container root filesystem read-only. Apple Container documents bind mounts with --mount and supports read-only mounts with the readonly option. citeturn831014search0turn831014search2

The runtime does not grant arbitrary host filesystem access: the workspace contract limits the writable host path before the container is created.

## Validation and evidence

- unit tests cover valid workspace creation, path escape, source mutability, output mutability, overlap, root/source identity, and symlink rejection.
- sandbox tests cover contract propagation and plan/contract path mismatch.
- pipeline tests require an explicit workspace root for runtime requests.
- CI remains the final compatibility gate across supported Python versions.

## Consequences

Positive:

- filesystem scope becomes an explicit typed contract instead of an implicit path convention.
- sandbox planning and execution share the same source/output identity.
- future quotas, cleanup, artifact retention, and output verification can attach to one workspace object.

Trade-off:

- callers must supply an explicit workspace root for capability execution.
- low-level sandbox callers may omit the explicit contract; the planner derives a bounded contract from the output parent for compatibility.

## Research notes

Apple Container documents host-directory bind mounts and read-only mount options. Named volumes and tmpfs have different persistence semantics; this step deliberately keeps the capability workspace as a task-owned host directory because the current runtime needs verified output files to remain available to the caller after execution. citeturn831014search0
