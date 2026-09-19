# ADR 0022: Brain-to-Runtime Capability Adapter

## Status

Accepted.

## Decision

Connect Brain routed steps to the disposable `CapabilityRuntime` through a dedicated adapter.

The adapter reads validated `RuntimeSpec` metadata from the selected registry entry, creates a unique output directory, forwards task constraints, and converts the runtime result into a bounded `RuntimeStepOutput`.

A capability without runtime metadata is rejected. The Brain remains unaware of sandbox implementation details.

OCI image references are treated as content-addressable when a `sha256:` digest is provided; OCI defines image manifests and configurations as content-addressed data. citeturn233020search1turn233020search4
