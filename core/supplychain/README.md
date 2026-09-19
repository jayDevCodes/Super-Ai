# Supply-chain controls

The supply-chain package is an additive admission layer around the existing registry.
It models immutable artifact identity, signatures, provenance, SBOM summaries, dependency
locks, revocation, deterministic trust scoring, mirror selection, registry reconciliation,
canonical fingerprints, and pluggable cryptographic verification adapters.

The core package never downloads or executes third-party code.
