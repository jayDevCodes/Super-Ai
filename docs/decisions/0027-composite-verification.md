# ADR 0027: Composite Verification Contracts

## Status

Accepted.

## Decision

Add composable verifier primitives so capabilities can require multiple independent correctness checks without changing the execution controller.

`AllOfVerifier` implements conjunction, `AnyOfVerifier` implements bounded alternative acceptance, and `PredicateVerifier` adapts deterministic predicates. Verifier exceptions fail closed.

Modern agent runtimes treat guardrails as an explicit validation stage around execution rather than implicit model confidence. citeturn889412search1turn889412search6

## Consequences

Verification rules are reusable, independently testable, and composable at the runtime boundary.
