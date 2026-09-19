# ADR 0022: Brain-to-Runtime Capability Adapter

## Status

Accepted.

## Decision

Connect the Brain's routed capability steps to the existing `CapabilityRuntime` through an adapter rather than coupling Brain to sandbox/staging implementation details.

The adapter reads the immutable manifest's `RuntimeSpec`, creates a unique disposable output directory for the execution, forwards the registry `CapabilitySpec` and task constraints to `CapabilityRuntime`, and returns bounded execution/evidence data to the Brain.

A capability without runtime metadata is rejected. No host-side import or execution of the staged repository is introduced.

Current runtime image identity follows the content-addressed OCI model: an optional immutable `sha256:` image digest can be carried with the manifest/runtime metadata and is later checked by the runtime preflight/attestation layer. OCI's Image Specification defines content-addressable manifests and platform-specific image manifests. citeturn233020search1turn233020search4

The adapter stays model-agnostic. A future intelligent router can choose among candidates, but executable runtime metadata remains explicit and validated before execution.

## Consequences

The control-plane path becomes:

`Brain -> Router -> RuntimeStepRunner -> CapabilityRuntime -> sandbox`.

The runtime layer remains independently replaceable while the Brain receives a typed execution result suitable for downstream DAG steps and audit evidence.
