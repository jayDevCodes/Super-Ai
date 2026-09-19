# ADR 0003: Ephemeral Capability Loader

## Decision

Introduce a lifecycle manager that loads one capability only after manifest validation and resource admission, stages it in an ephemeral workspace, keeps it active only for the task, and releases resources plus temporary storage during unload.

The loader intentionally does not fetch or execute arbitrary GitHub repositories itself. Source retrieval, artifact verification, and sandbox execution remain explicit injected boundaries. This prevents the lifecycle component from becoming a trust bypass.

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

## Design implications

- GitHub remains the durable source/registry.
- Local runtime storage is disposable.
- Resource reservations use the existing peak-RAM scheduler.
- Capability identity and version must agree between manifest and runtime spec.
- A staging failure must release both resource reservations and temporary storage.
- Cleanup must release resources even when capability cleanup raises an error.

## Next hardening step

Implement a real GitHub/artifact resolver behind the staging interface. It must pin a commit/tag, verify artifact integrity, enforce sandbox/network policy, and apply time/resource limits before executing third-party code.
