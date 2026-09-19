# ADR 0015: Dependency-Aware Task DAG Executor

## Status

Accepted.

## Decision

Add a task executor that consumes the existing validated `Task` DAG and runs ready steps with bounded parallelism.

The executor uses Python's `TopologicalSorter` state machine and a bounded `ThreadPoolExecutor`. Ready steps may run concurrently only within the task's `max_parallelism` and executor worker limit.

A failed step stops downstream scheduling. Results are returned in deterministic step-ID order.

## Consequences

Super-Ai now has a concrete execution engine for the task DAG rather than only a schema. Capability handlers remain injected, keeping capability selection and sandbox execution separate from graph coordination.
