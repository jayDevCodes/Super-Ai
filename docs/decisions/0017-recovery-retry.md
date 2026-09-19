# ADR 0017: Bounded Recovery and Retry Policy

## Status

Accepted.

## Decision

Automatic retry is allowed only for classified transient failures and only when the operation is explicitly marked idempotent.

The retry budget is bounded by a maximum attempt count. Delays use capped exponential backoff with optional full jitter.

Timeout/resource failures, verification failures, cleanup failures, and security failures are not retried by this layer.

## Consequences

Recovery becomes explicit and measurable instead of allowing arbitrary retry loops. Higher layers may choose an alternate capability or human escalation after the retry budget is exhausted.
