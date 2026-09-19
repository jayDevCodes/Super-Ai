# ADR 0031: Benchmark execution metadata projection

## Status

Accepted.

## Context

Super-Ai already returns an ExecutionResult with execution status, exit code, duration, timeout/truncation flags, verification and sandbox evidence. Control-plane audit paths need small metadata records and must not accidentally carry stdout, stderr, or raw telemetry.

Current OpenTelemetry guidance recommends capturing only attributes that add clear value and keeping telemetry overhead low. Python's monotonic performance-counter APIs are intended for measuring short durations, and monotonic_ns() avoids float precision loss.

## Decision

Add ExecutionResult.as_metadata() as the canonical bounded control-plane projection. It includes only scalar execution and sandbox identity fields and deliberately excludes stdout, stderr, and raw telemetry.

Add a dependency-free benchmark harness under benchmarks/benchmark_execution_metadata.py. It measures:

- ExecutionResult construction.
- Metadata projection.

The harness uses time.perf_counter_ns(), configurable warmup/iteration counts, and reports median, p95, min, and max nanoseconds. It is intentionally not a CI performance gate because hosted-runner noise is not representative of the target-class 8 GB RAM / 256 GB environment.

## Validation

Unit tests verify metadata exclusion and benchmark output shape. CI remains the correctness gate.

## Research basis

- OpenTelemetry Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/how-to-write-conventions/
- Python time module: https://docs.python.org/3/library/time.html

## Limitations

Benchmark numbers from GitHub-hosted runners must not be treated as target-hardware performance evidence. Target-class measurements should be collected on the user's actual execution hardware before changing runtime or model weight.
