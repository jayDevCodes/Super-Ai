# ADR 0030: Enforce Verification-Required Capabilities

## Status

Accepted.

## Decision

When a capability declares `verification_required=True`, `CapabilityRuntime` refuses to execute unless an explicit verifier is supplied.

This turns the existing capability contract into an enforced runtime invariant. Modern agent runtimes expose guardrails as explicit input/output validation stages rather than treating model confidence as proof. citeturn889412search1turn889412search6

## Consequences

A capability cannot accidentally produce an accepted result with `verified=None` when its contract requires verification. A capability may explicitly opt out by setting `verification_required=False`.
