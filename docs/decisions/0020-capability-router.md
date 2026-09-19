# ADR 0020: Deterministic Capability Router

## Status

Accepted.

## Decision

Add a deterministic capability router over the validated registry and policy engine.

Routing occurs only among capabilities that satisfy required permissions and policy. Exact `capability_id` matches receive a strong priority. Otherwise, semantic token overlap across capability metadata and required-permission matches provide a stable score.

Capabilities denied by policy are removed before ranking. Confirmation-requiring capabilities can be requested explicitly but are not selected for automatic execution unless the caller opts in to confirmation candidates.

No LLM is required for this router. A future model-assisted router may rank only the already policy-compatible candidate set.

## Consequences

Routing becomes reproducible, testable, and auditable while preserving a clean insertion point for a future learned ranker.
