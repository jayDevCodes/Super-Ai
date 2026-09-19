# ADR 0008: Resource Leases and Execution Sessions

## Context

Super-Ai now has resource admission, source staging, sandbox planning, and an execution controller. These components must share one lifecycle so a worker cannot start without resource admission and an exception cannot strand a RAM/CPU/disk reservation.

The scheduler also needs to remain correct when several task workers attempt admission concurrently.

## Decision

Introduce a thread-safe ResourceLease and ExecutionSession.

ResourceScheduler now protects admission, reservation, allocation counters, and release with a re-entrant lock. The admission check and allocation insertion occur inside one critical section.

ResourceLease is a context-managed, idempotent release handle:

    with scheduler.lease(...):
        ...

ExecutionSession binds one resource lease to one execution controller run. Resources are acquired before launch and released only after the execution controller has finished process termination, result verification, and cleanup.

The execution controller subprocess adapter is also corrected to consume Popen.stdout and Popen.stderr as stream attributes. A real subprocess integration test covers this path.

## Lifecycle

    Scheduler lease
          ↓
    ExecutionSession
          ↓
    SandboxPlan
          ↓
    ExecutionController
          ↓
    process termination / verification / cleanup
          ↓
    ResourceLease release

## Invariants

- Admission plus reservation is atomic with respect to concurrent scheduler callers.
- A lease can be safely released more than once.
- A session cannot execute before entering its context.
- A session is single-use.
- Resource release occurs after controller cleanup, including controller failure paths.
- Unverified sandbox plans remain blocked by the existing execution_ready gate.

## Next step

Connect the session to a real sandbox lifecycle backend and make the sandbox executor the only production route to untrusted capability execution.
