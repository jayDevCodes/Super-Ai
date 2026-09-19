# ADR 0018: Hash-Chain Audit Evidence

## Status

Accepted.

## Decision

Record trusted control-plane lifecycle events as bounded JSON Lines with a SHA-256 hash chain.

Each event has a sequence number, UTC timestamp, event name, sanitized attributes, previous hash, and event hash. Verification recomputes every event hash and checks the sequence and chain linkage.

This provides tamper detection and a compact audit trail; it is not a remote immutable ledger and does not provide non-repudiation by itself.

Untrusted stdout/stderr remains execution output rather than trusted audit evidence.

## Consequences

Runtime, policy, routing, recovery, and verification layers can emit correlated, structured evidence without introducing an external logging dependency. The store remains local and bounded at the individual event level; retention policy is a separate concern.
