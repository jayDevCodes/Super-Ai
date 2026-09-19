# ADR 0021: Lightweight Brain Orchestrator

## Status

Accepted.

## Decision

Add a lightweight control-plane Brain that plans each validated Task step through the deterministic capability router and executes the resulting DAG through the existing TaskExecutor.

The Brain is intentionally model-agnostic. A future LLM can propose or refine tasks, but the router and policy engine remain authoritative over executable capability selection.

Consequential capabilities may produce a confirmation requirement. Brain execution rejects those tasks until explicit confirmation is supplied.

Optional hash-chain audit evidence records planning, execution start/finish, and step completion events.

## Consequences

Super-Ai now has a concrete control-plane loop:

`Task -> Brain.plan -> Policy-constrained Router -> TaskExecutor -> injected capability runner`.

The capability runner can later be backed by `CapabilityRuntime` so the Brain remains unaware of sandbox and staging implementation details.
