# Syscall posture

Super-Ai defaults every sandbox profile to `SyscallMode.RESTRICTED`. The
profile is compiled into deterministic runtime intent (`--syscall-mode=restricted`)
and included in hardening evidence before a worker can start.

The policy has two deliberately separate responsibilities:

- **Control plane:** validate that a profile has an allowed posture and record
  the selected mode in the deterministic fingerprint.
- **Runtime adapter:** translate that intent into the host/container mechanism
  available on the target (for example, a seccomp or Apple Container policy),
  then attest the created runtime before execution.

The translation layer does not claim that emitting an argument enforces a
kernel policy. A runtime that cannot honor the requested restricted posture
must fail closed rather than silently fall back to `default`. Model size,
quantization or task urgency cannot relax this boundary.

Changing the default or adding a syscall profile requires a decision record,
focused profile/translation tests, runtime-specific evidence and compatible
host integration validation.
