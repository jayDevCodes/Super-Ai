# ADR 0033: Benchmark ownership verification

## Status

Accepted.

## Context

Super-Ai uses a unique execution ID plus ownership labels to prevent stale or unrelated containers from being deleted by an execution cleanup path.

Apple Container exposes detailed machine-readable JSON from `container inspect`, which makes an ownership check suitable for deterministic parsing before destructive cleanup. citeturn418823search0turn418823search8

## Decision

Add a dependency-free benchmark covering two hot-path ownership operations:

- `new_ownership_claim()` creation.
- `verify_container_ownership()` against representative JSON inspect data.

The benchmark uses `time.perf_counter_ns()`, which Python documents as a high-resolution counter for short-duration measurement and provides a nanosecond form without float precision loss. citeturn418823search1

Timing thresholds are informational and are not used as a CI pass/fail gate because hosted runner timing is noisy. Target-class hardware measurements should be collected before making performance-driven architectural changes.

## Validation

Unit tests verify benchmark configuration, output shape, and basic non-negative timing values. Existing ownership security tests remain unchanged.

## Limitations

This benchmark measures local Python claim/verification work. It does not measure the latency of the real `container inspect` CLI or VM/container lifecycle.
