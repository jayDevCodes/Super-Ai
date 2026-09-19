# ADR 0038: Execution Cancellation Integration

## Status

Accepted — step 29.

## Decision

Introduce a thread-safe, one-shot `CancellationToken` and propagate it from brain context → runtime request → execution session → execution controller.

Cancellation is represented by a distinct `ExecutionStatus.CANCELLED` result. The controller checks the token while waiting for the workload and, when cancellation is requested, uses the existing graceful-stop path before falling back to kill after the configured grace period. Cleanup remains mandatory.

The token records one bounded reason; later cancellation requests do not overwrite the first reason.

## Research

Python's `threading.Event` is designed for one thread to signal another and provides `set()` and `is_set()` semantics suitable for a low-overhead cancellation signal. citeturn710470search0

Apple Container exposes graceful `container stop` with a configurable timeout and an immediate `container kill`; the runtime already maps those lifecycle operations through its sandbox process handle. citeturn710470search2

## Invariants

- cancellation never disables sandbox cleanup.
- timeout and cancellation are distinct statuses.
- cancellation reason is bounded and does not carry stdout/stderr.
- existing resource leases remain owned by the execution session until controller cleanup completes.
- the brain can supply a cancellation token through its runtime context without gaining a new host-execution capability.

## Validation

Tests cover token first-writer semantics, active cancellation of a running process, pre-cancelled execution behavior, metadata propagation, and pipeline propagation.
