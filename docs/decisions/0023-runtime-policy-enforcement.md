# ADR 0023: Runtime Policy Enforcement

## Status

Accepted.

## Decision

Enforce the capability policy again inside `CapabilityRuntime`, immediately before source staging.

The router is not a security boundary by itself. Runtime execution must independently check the capability's permissions, resource ceilings, network eligibility, and confirmation state before any untrusted source is staged.

This is defense in depth and follows established authorization guidance to enforce access control at the point where the protected operation occurs, deny by default, test authorization rules, and avoid relying on a single control. citeturn773050search0turn773050search7

## Consequences

A capability cannot bypass policy merely by calling the runtime directly instead of going through Brain/Router. The runtime becomes a genuine policy enforcement point for capability execution.
