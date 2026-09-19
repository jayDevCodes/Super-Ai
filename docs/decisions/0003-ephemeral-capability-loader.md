# ADR 0003: Ephemeral Capability Loader

## Decision

Introduce a lifecycle manager that loads one capability only after manifest validation and resource admission, stages it in an ephemeral workspace, keeps it active only for the task, and releases resources plus temporary storage during unload.

The loader deliberately does not clone or execute arbitrary GitHub code itself. A trusted staging/factory implementation is injected at the boundary so source retrieval, sandboxing, and artifact verification can be hardened independently.

## Lifecycle

registry manifest
-> validate identity/version/source
-> resource admission
-> temporary workspace
-> trusted staging/factory
-> active capability
-> execute/verify
-> cleanup
-> release resources

## Security invariant

External code is addressable by a GitHub repository URL plus an immutable commit SHA. A moving branch/tag is not accepted as the registry identity. Artifact checksums are optional at this layer and must be enforced by the later staging/artifact verifier when an artifact is available.

## Design implications

- GitHub remains the durable source/registry.
- Local runtime storage is disposable.
- Resource reservations use the existing peak-RAM scheduler.
- Capability identity and version must agree between manifest and runtime spec.
- A staging failure must release both resource reservations and temporary storage.
- Cleanup must release resources even when capability cleanup raises an error.
- Lifecycle code never becomes a trust bypass for arbitrary downloaded code.

## Next hardening step

Implement a real GitHub/artifact resolver behind the staging interface. It must resolve the pinned commit, verify artifact integrity, enforce sandbox/network policy, and apply time/resource limits before executing third-party code.
