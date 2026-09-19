# ADR 0012: End-to-End Capability Runtime Pipeline

## Status

Accepted.

## Decision

Connect the existing immutable resolver, secure stager, resource lease/session, sandbox planner, Apple Container executor, verification, and cleanup layers through one explicit `CapabilityRuntime` orchestration boundary.

The runtime sequence is:

`manifest validation -> immutable source resolution -> secure staging -> policy-derived sandbox plan -> resource lease -> isolated execution -> verification -> cleanup -> disposable staged-source teardown`

The pipeline deliberately keeps the staged source ephemeral and does not import or execute it on the host.

## Network rule

Network access remains disabled unless both the task explicitly permits network access and the capability declares a `network` permission. The sandbox still requires an explicit network mode and a non-root user.

## Consequences

Callers no longer need to manually wire the lower-level components for every capability execution. The lower layers remain independently testable and replaceable.

The first implementation targets the Apple Container backend; other sandbox backends can be added without changing the request/verification boundary.
