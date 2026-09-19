# ADR 0007: Bounded Execution Controller

## Context

Super-Ai now has resource admission, immutable source staging, and a sandbox plan. The remaining runtime gap is lifecycle control: starting an already-sandboxed command, bounding output, enforcing a deadline, collecting exit status, verifying the result, and guaranteeing cleanup.

## Decision

Introduce an ExecutionController with:

- immutable ExecutionPolicy limits;
- shell-free argv launch through an injected ProcessLauncher;
- an explicit environment allowlist rather than inheriting all host environment variables;
- bounded stdout/stderr capture in memory;
- timeout watchdog using process termination followed by kill when necessary;
- POSIX process-group termination when the underlying process is a real subprocess;
- explicit status values for completed, failed, timed out, verification failed, and cleanup failed executions;
- optional result verifier;
- mandatory cleanup callback support through a finally-style lifecycle.

The controller refuses a SandboxPlan whose execution_ready flag is false. Therefore, the default network-disabled Apple Container planner cannot accidentally become executable through this controller until a backend establishes and verifies actual network denial.

## Output and memory safety

Output is capped independently for stdout and stderr. Excess bytes are discarded and reported with truncation flags. The controller therefore does not retain unbounded command output in RAM.

## Security boundary

The controller does not decide whether a source is trustworthy and does not create a sandbox itself. It accepts an already-built SandboxPlan and launches only the plan's argv. Staging, sandbox selection, and execution remain separate responsibilities.

## Next step

Add a real, verified network-disabled sandbox executor and connect scheduler allocations to execution lifecycle so resources are reserved before launch and released after cleanup.
