# Decision 0042 — Sandbox security posture

Status: accepted

A dedicated SecurityProfile models mandatory non-root execution, no-new-privileges,
restricted syscall posture, read-only root filesystem, explicit write roots,
deny-by-default networking, bounded process/file quotas, and constrained capabilities.

OwnershipFence adds a stale-cleanup race barrier. These controls are pure contracts;
the existing Apple Container executor remains responsible for translating them into
runtime-specific flags. Linux CI validates policy semantics, while actual Apple
Container behavior remains opt-in on compatible hardware.
