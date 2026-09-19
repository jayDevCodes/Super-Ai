# ADR 0035: Benchmark image identity

## Status

Accepted.

## Context

Super-Ai resolves an image tag/reference through the Apple Container CLI and requires a valid SHA-256 digest before execution. OCI defines a descriptor digest as a content identifier and states that content can be independently verified by recalculating the digest; the Distribution specification further recommends verification when a manifest is requested by digest. citeturn609897search4turn609897search2

## Decision

Add a dependency-free benchmark covering local digest validation and representative image-identity resolution from machine-readable inspect JSON.

Use `time.perf_counter_ns()` for short-duration measurements and keep timing informational rather than a CI threshold.

## Validation

Unit tests validate benchmark shape and configuration rejection. Existing preflight tests remain the correctness gate.

## Limitations

The resolution benchmark uses an in-process fake command runner and therefore excludes real CLI, registry, disk, and Apple Container latency.
