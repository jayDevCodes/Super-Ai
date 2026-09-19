# Decision 0045 — Security evidence and cleanup fencing

Status: accepted

The security posture produces deterministic evidence for audit correlation, while runtime
cleanup uses a separate ownership fence so stale cleanup cannot act on a replaced resource.

The fence is intentionally small and in-process; durable container ownership remains the
source of truth at the runtime boundary.
