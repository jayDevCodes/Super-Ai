# ADR 0029: Runtime Trace Context Propagation

## Status

Accepted.

## Decision

Carry immutable trace context from a capability runtime request into trusted runtime audit events.

A supplied trace context is preserved across runtime lifecycle events; nested lifecycle events receive child span IDs while retaining the same trace ID.

OpenTelemetry defines immutable span context for propagation across execution boundaries, and its log model supports trace and span IDs for correlation. citeturn932278search1turn932278search10

## Consequences

Brain, runtime, telemetry, and audit events can be correlated without coupling the core to a particular tracing SDK.
