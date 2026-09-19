# ADR 0028: Runtime Audit Integration

## Status

Accepted.

## Decision

The capability runtime emits bounded control-plane audit events for execution request, policy denial, start, and finish.

Audit attributes contain only metadata needed for correlation and security evidence: capability ID/version, image reference, result status, verification state, cleanup state, attestation state, and resolved image digest. Untrusted stdout/stderr is deliberately excluded.

OpenTelemetry recommends correlating logs/events with execution context and structured semantic attributes; Super-Ai keeps the current implementation dependency-free and writes to its existing hash-chain audit store. citeturn932278search10turn932278search18

## Consequences

Direct runtime callers receive the same audit visibility as Brain-routed callers without exposing untrusted capability output through the trusted audit channel.
