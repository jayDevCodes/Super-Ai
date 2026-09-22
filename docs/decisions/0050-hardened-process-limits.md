# Decision 0050 — Hardened process limits

Status: accepted

## Context

Super-Ai already represented process and open-file quotas in SecurityProfile and translated
the process quota to Apple Container `--ulimit nproc`. Step 133 closes the remaining
runtime contract gap: the sandbox must carry both limits, and the created container must
prove that its init-process rlimits match the requested values before it can start.

## Decision

The runtime process-limit contract now:

- bounds process limits to 1..4096;
- bounds open-file limits to 16..65536;
- carries `max_processes` and `max_open_files` through SandboxPolicy;
- emits exact Apple Container `--ulimit nproc=N:N` and `--ulimit nofile=M:M` intent;
- includes both limits in the execution contract fingerprint;
- attests `initProcess.rlimits` after container creation and before start;
- requires both soft and hard limits to match the requested values;
- rejects duplicate/malformed rlimit records and fails closed when a required limit is missing;
- exposes the attested limits through SandboxAttestation evidence.

Apple Container's current resource model represents these as Linux resource limits:
`RLIMIT_NPROC` and `RLIMIT_NOFILE`. Its inspect representation exposes them under
`configuration.initProcess.rlimits`, and its integration tests verify `nproc` and
`nofile` values after creation.

The project intentionally does not invent a container-wide `--pids-limit` flag for Apple
Container. Runtime telemetry may still report observed process counts, but process-count
telemetry is not treated as equivalent to the configured rlimit.

## Validation

Focused tests cover:
- sandbox command emission;
- process/open-file policy bounds;
- valid rlimit attestation;
- missing, malformed, duplicate, and mismatched rlimits;
- fail-closed executor behavior before container start.

The repository CI matrix is used for Python 3.11, 3.12, and 3.13. Real Apple Container
behavior remains opt-in on compatible Apple Silicon hardware.

## Limitations

`RLIMIT_NPROC` is a Linux UID-scoped limit on processes/threads rather than a universal
container PID counter. Because Super-Ai requires non-root execution and drops all
capabilities, it is a meaningful enforcement boundary for the current runtime, but future
multi-UID workloads would need an additional aggregate PID control.
