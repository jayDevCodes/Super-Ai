# Decision 0040 — Runtime-spec hardening

Status: accepted

The existing RuntimeSpec contract remains the compatibility boundary. A new additive
RuntimeSpecGuardian performs a second, fail-closed review for autonomous execution.

The guardian requires an immutable image digest by default, bounds argv/token size,
restricts working directories to explicit roots, canonicalizes fields, and emits a
stable SHA-256 fingerprint. It does not silently rewrite the existing RuntimeSpec.

This preserves callers while giving the execution pipeline a stronger admission gate.
