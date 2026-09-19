# ADR 0038: Execution Idempotency

## Status

Accepted — step 30.

## Decision

Add a process-local idempotency coordinator at the capability runtime boundary.

A caller may provide an explicit idempotency key. The runtime derives a SHA-256 fingerprint from the stable execution semantics: capability identity/version, image, command, pinned image digest when present, workspace paths, timeout, effective network mode, and output contract. Volatile trace and cancellation state are deliberately excluded.

For a given key:

- the first matching request owns the execution claim;
- a concurrent identical request waits and then replays the recorded terminal result;
- a completed request with the same key and a different fingerprint is rejected;
- failed setup/execution paths release the claim;
- completed entries are bounded by count and TTL;
- replay output is byte-bounded before storage;
- the raw idempotency key is not written into audit events.

The coordinator is intentionally process-local in this step. Durable cross-process storage and crash-recovery semantics remain later hardening work.

## Runtime integration

`CapabilityExecutionRequest` now accepts `idempotency_key`. The capability runtime claims the key after policy, workspace, and output-contract validation and before sandbox execution. On replay, the cached terminal result is returned without running the controller a second time.

The brain runtime runner accepts `__idempotency_key` in execution context. When supplied, it derives a stable workspace subdirectory from a SHA-256 digest of the key so repeated logical executions address the same workspace instead of generating a new UUID path.

This design prevents accidental duplicate execution at the runtime boundary while keeping retries without a supplied key independent.

## Research basis

RFC 9110 defines an idempotent request method in terms of repeated identical requests having the same intended server effect and explains why idempotence enables safe automatic retries after communication failures. The runtime applies the same principle explicitly to a logical capability execution keyed by caller intent rather than assuming every execution command is inherently idempotent. citeturn710470search0turn710470search8

## Validation

- unit tests cover replay, fingerprint conflict, abort/retry, concurrent deduplication, bounds, invalid keys/fingerprints, deterministic fingerprints, and runtime replay.
- brain runtime tests verify a supplied idempotency key produces a stable workspace path.
- full GitHub Actions matrix remains required before merge.

## Consequences

Positive:

- duplicate task submission cannot launch the same keyed capability twice within one runtime process.
- the request semantics are bound cryptographically, so key reuse for a different operation fails closed.
- replay memory is bounded.

Trade-offs:

- state is lost on process restart.
- callers must keep the same logical key and workspace path semantics for replay.
- storing only bounded terminal evidence means replay is a control-plane result, not a new execution.
