# ADR 0032: Benchmark RuntimeSpec validation

## Status

Accepted.

## Context

RuntimeSpec is validated at the capability execution boundary before staging and sandbox execution. The validation contract protects image references, argv tokens, timeout bounds, optional image digests, and working-directory shape.

OCI describes image digests as content identifiers and recommends verifying a manifest returned by a digest reference against that digest. This supports keeping image identity validation explicit even when the benchmark itself only measures local contract-validation cost.

## Decision

Add a dependency-free benchmark harness for the steady-state RuntimeSpec.validate() path using a representative bounded specification. The harness reports median, p95, minimum, and maximum validation time in nanoseconds and uses Python's performance counter.

Do not make CI pass/fail on absolute timing thresholds. Hosted runners are variable, and the Super-Ai performance rule requires target-class measurements before increasing runtime or model weight.

## Validation

Unit tests cover benchmark configuration and output shape. CI remains the correctness gate.

## Research basis

- OCI Distribution Specification: https://github.com/opencontainers/distribution-spec
- OCI Image Descriptor digests: https://github.com/opencontainers/image-spec/blob/main/descriptor.md
- Python time module: https://docs.python.org/3/library/time.html

## Limitations

This benchmark measures Python contract validation only. It does not measure registry pulls, image resolution, sandbox startup, or Apple Container performance.
