# ADR 0016: Telemetry-Driven Resource Feedback

## Status

Accepted.

## Decision

Use measured execution telemetry to produce conservative resource recommendations without silently rewriting declared capability limits.

The controller keeps a bounded history per capability, applies a configurable safety factor to measured peak memory, and derives a conservative parallelism ceiling from observed CPU consumption and execution RAM capacity.

When there is no history, the recommendation remains conservative: one parallel execution using the declared RAM budget.

Recommendations are advisory until the scheduler or policy layer explicitly accepts them.

## Consequences

Super-Ai can learn from actual workload behavior while preserving deterministic admission and avoiding feedback loops that silently expand permissions or resource limits.
