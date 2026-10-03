# Decision 0052 — Hardened race fence

Status: accepted

## Context

Cleanup and replacement operations share resources whose ownership can change
between task attempts. A fence must validate token shape, serialize claims and
make the check-and-mutate operation atomic; callers should not implement that
sequence themselves.

## Decision

`OwnershipFence` now validates token and owner identifiers, performs release in
one lock-held compare-and-remove operation, and exposes `replace()` for an
atomic ownership handoff. A handoff creates a fresh nonce and invalidates the
old token. Concurrent acquisition remains single-winner. This is process-local
state; cross-process recovery still requires a durable ownership protocol.

## Validation

Focused tests cover stale-token invalidation after replacement, concurrent
single-winner acquisition, identifier validation and normal cleanup release.
