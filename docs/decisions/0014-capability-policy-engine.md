# ADR 0014: Capability Policy Engine

## Status

Accepted.

## Decision

Introduce a deterministic policy engine between capability selection and execution.

Policy is deny-by-default. A capability can execute only when its declared permissions are allowlisted and its resource contract fits policy ceilings.

Network access additionally requires both a capability `network` permission and a task-level `allow_network` flag.

Permissions representing consequential external actions (for example `submit`) return a confirmation decision when the task requires confirmation.

## Consequences

Policy decisions become explicit, testable, and independent from model output. The runtime can record the decision and reason for each execution.

This follows least-privilege and deny-by-default access-control principles.