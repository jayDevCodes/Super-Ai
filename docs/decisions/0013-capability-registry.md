# ADR 0013: Deterministic Capability Registry

## Status

Accepted.

## Decision

Add a typed registry that treats a capability's source manifest and execution specification as one validated versioned entry.

The registry supports exact `capability_id@version` lookup, unambiguous single-version lookup, deterministic metadata search, duplicate rejection, and JSON loading.

Registry records remain metadata only. The registry never imports or executes a capability.

The companion JSON Schema uses the current JSON Schema 2020-12 dialect. Runtime validation remains explicit in Python so the core has no mandatory third-party schema dependency.

## Consequences

The router can select capabilities from one authoritative catalog while the immutable Git source reference remains part of the manifest. Future remote registries can feed the same typed entry boundary.
