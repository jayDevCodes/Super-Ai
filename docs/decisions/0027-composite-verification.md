# ADR 0027: Composite Verification Contracts

## Status

Accepted.

## Decision

Add composable verifier primitives so capabilities can require multiple independent correctness checks without changing the execution controller.

`AllOfVerifier` implements conjunction, `AnyOfVerifier` implements bounded alternative acceptance, and `PredicateVerifier` adapts deterministic predicates. Exceptions are converted to a verification failure via a dedicated error so callers do not accidentally treat verifier errors as success.

The design mirrors modern agent guardrail composition: validation remains a separate, explicit stage around execution rather than relying on model confidence alone. Current agent SDK documentation explicitly treats guardrails as validation of agent inputs and outputs. citeturn889412search1turn889412search6

## Consequences

Verification rules become reusable and independently testable while preserving fail-closed behavior at the execution boundary.
