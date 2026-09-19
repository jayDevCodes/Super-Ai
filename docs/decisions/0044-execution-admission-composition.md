# Decision 0044 — Composed execution admission

Status: accepted

Runtime specification hardening, sandbox hardening, and third-party supply-chain evidence
are independent gates. ExecutionAdmissionGate composes them without coupling policy
implementation to a runtime-specific container command.

For existing smoke tests the supply-chain requirement is optional. Autonomous
third-party execution can set require_artifact=True and therefore fails closed when
artifact evidence is absent.
