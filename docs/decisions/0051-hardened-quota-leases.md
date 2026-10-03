# Decision 0051 — Hardened quota leases

Status: accepted

## Context

The original `QuotaLedger` held aggregate arithmetic only. It could reject an
over-capacity request, but it did not provide an identity for a reservation or
protect the read/check/update path from concurrent callers.

## Decision

Step 134 adds an in-memory lock and opaque, single-use `QuotaReservation`
leases. `reserve_lease()` atomically admits and records a quota; `release_lease()`
requires the original identifier and exact resource tuple. An unknown, reused or
mismatched lease fails closed and leaves the reservation intact. The existing
`reserve()` / `release()` API is retained for compatibility with simple
single-owner callers.

Leases are process-local and intentionally do not claim crash recovery or
cross-process coordination. The runtime must still release owned work during
its cleanup lifecycle; future scheduler steps can persist leases only with an
explicit ownership/expiry contract.

## Validation

Focused tests cover regular reserve/release, capacity overflow, exact
single-use releases and mismatched-lease rejection.
