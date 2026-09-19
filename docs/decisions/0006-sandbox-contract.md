# ADR 0006: Sandbox Contract and Apple Container Planner

## Context

The secure stager now materializes untrusted capability source into an ephemeral workspace. The next boundary must keep source execution separate from the host and from the stager.

Apple's current container CLI runs containers in lightweight virtual machines and exposes CPU/memory resource controls, read-only roots, bind mounts, capability dropping, process limits, and network configuration. Network behavior varies by macOS release, so the runtime must not invent a network=none option that the CLI does not document.

## Decision

Introduce a backend-neutral SandboxPolicy and immutable SandboxPlan.

The first backend is an Apple Container command planner. It:

- uses --rm for automatic container removal;
- uses a read-only root filesystem;
- drops all Linux capabilities;
- applies CPU, memory, and process-count limits;
- mounts capability source read-only;
- mounts only an explicit workspace read-write;
- optionally selects a named network;
- never passes host environment variables implicitly;
- produces an argv array rather than a shell string.

The planner deliberately does not launch processes.

For the default network=disabled policy, the plan is marked execution_ready=false. We will not pretend that omission of a network flag means zero network access. A later executor must establish and verify true network denial before untrusted source can run.

## Why this fits the 8 GB target

Resource limits are applied at the sandbox boundary and remain separate from the scheduler. A scheduler can reserve RAM/CPU before a plan is built, while the sandbox enforces the requested ceiling inside the isolation boundary.

## Next step

Implement the execution controller: admission -> sandbox launch -> timeout/kill -> result capture -> verifier -> cleanup, with a real network-disabled backend and integration tests.
