# ADR 0024: Trace Context Primitive

## Status

Accepted.

## Decision

Introduce an immutable `TraceContext` primitive with a 32-hex-character Trace ID and a 16-hex-character Span ID, plus optional parent span and trace flags.

The representation aligns with OpenTelemetry's SpanContext shape and W3C Trace Context identifier formats. OpenTelemetry specifies a 16-byte Trace ID and 8-byte Span ID and requires immutable SpanContext values; W3C Trace Context standardizes context propagation between distributed components. citeturn932278search1turn932278search0

Super-Ai does not add a full OpenTelemetry dependency yet. The primitive gives audit and runtime layers a stable correlation contract that can later map directly to OpenTelemetry.

## Consequences

Every major lifecycle can be correlated without exposing task contents or untrusted execution output. Child spans preserve the same trace ID while receiving a new span ID.
