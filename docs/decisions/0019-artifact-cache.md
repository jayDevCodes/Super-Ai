# ADR 0019: Content-Addressed Artifact Cache

## Status

Accepted.

## Decision

Add a local content-addressed artifact cache keyed by SHA-256, with atomic writes, integrity checks on reads, bounded total size, and least-recently-used eviction.

The cache stores disposable artifacts only. It does not store secrets, credentials, or trusted authorization state.

A cache hit is accepted only after the file bytes re-hash to the requested digest. Metadata corruption fails closed.

## Consequences

Repeated capability downloads and generated intermediate artifacts can be reused without keeping every source permanently. The cache has an explicit byte ceiling so it remains compatible with the 256 GB target machine.

This is an application-local cache and does not rely on GitHub Actions cache storage.
