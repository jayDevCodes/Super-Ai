# ADR 0034: Benchmark container lifecycle orchestration

## Status

Accepted.

## Context

Super-Ai's Apple Container executor coordinates preflight, image identity, container creation, inspect/attestation, start, telemetry, stop/kill, and ownership-checked deletion. Apple documents create as producing a stopped container, start as starting a stopped container, stop/kill as lifecycle controls, and delete as removal; inspect exposes detailed JSON for scripting. citeturn687742search1

## Decision

Add a dependency-free benchmark around the executor's control-plane lifecycle using an in-process fake command runner. The benchmark exercises the orchestration path without launching a real VM or deleting real user containers.

The benchmark uses `time.perf_counter_ns()` for short-duration measurements. citeturn687742search2

Absolute timings are informational. They are not a CI threshold because hosted runners do not represent the real Apple Silicon + Apple Container environment.

## Validation

Unit tests validate the benchmark result shape and configuration errors. Existing lifecycle, attestation, ownership, and timeout tests remain the correctness gate.

## Limitations

This benchmark excludes actual Apple Container CLI latency, VM startup, image resolution, filesystem I/O, and network behavior. Real runtime measurements must be performed on a supported Apple Silicon host or self-hosted runner.
