# ADR 0029: Runtime Trace Context Propagation

## Status

Accepted.

## Decision

Carry the immutable trace context from the capability runtime request into trusted runtime audit events.

A caller may supply an existing trace context; otherwise the runtime creates a root context. Lifecycle events reuse the trace ID while creating child span IDs for nested runtime phases.

OpenTelemetry defines span contexts as immutable and designed for propagation across execution boundaries; trace and span identifiers are the primary correlation fields. citeturn932278search1turn932278search7

## Consequences

Brain, runtime, telemetry, and audit layers can correlate one capability execution without coupling the core to a particular telemetry SDK.
