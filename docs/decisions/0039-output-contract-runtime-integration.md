# ADR 0039: Output Contract Runtime Integration

## Status

Accepted — step 28 repair.

## Decision

Treat output validation as part of the runtime acceptance boundary, not only as a standalone contract.

A capability runtime request may provide an explicit `OutputContract`. When omitted, the runtime inherits the manifest's `RuntimeSpec.output_contract`; a conservative default contract is used when neither is present.

After execution completes, the runtime inspects the declared workspace output without following symbolic links. A completed execution whose output contract fails is converted to `ExecutionStatus.VERIFICATION_FAILED` with `verified=False`. Bounded output evidence is attached to `ExecutionResult` and its control-plane metadata projection.

Runtime registry JSON now carries the output contract inside `manifest.runtime.output_contract`, so a capability's required artifacts and size/count limits travel with the immutable runtime specification.

## Security and resource invariants

- required output paths are relative and reject NUL/newline/control characters.
- absolute paths and `..` traversal are rejected.
- output symlinks are rejected.
- inspection does not follow symlink directories.
- file-count and total-byte limits stop traversal once the contract is exceeded.
- violation evidence is capped at 32 entries.
- output metadata excludes file contents.

Python documents that `os.walk(..., followlinks=False)` does not descend into directory symlinks by default, which supports the non-following traversal used here. citeturn568859search0

OWASP describes path traversal as a class of attacks that can reach filesystem locations outside an intended root; rejecting absolute and parent-directory path segments is part of the runtime output contract boundary. citeturn568859search6

## Consequences

Positive:

- successful execution now requires both process-level acceptance and declared output integrity.
- capability manifests can describe their expected artifacts and bounded output envelope.
- output inspection is resource-bounded and fail-closed.

Trade-off:

- a capability that exits successfully can now be reported as verification failure when its declared outputs are absent or exceed limits.
- output inspection is currently performed at the end of the process-local execution; durable artifact manifests and persistent receipts remain future hardening work.

## Validation

The repair adds tests for registry round-trip, runtime-spec validation, control characters, bounded violation evidence, output metadata, successful required outputs, and fail-closed missing outputs. The full CI matrix remains the merge gate.
