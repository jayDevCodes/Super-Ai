# Supply-chain controls

The supply-chain package is an additive admission layer around the existing registry.
It models immutable artifact identity, signature/provenance/SBOM/dependency-lock evidence,
revocation, deterministic trust scoring, registry reconciliation, and pluggable
verification.

No module in this package downloads or executes third-party code. Runtime adapters
remain responsible for translating an admitted record into staging/execution actions.
