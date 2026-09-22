# Decision 0049 — Hardened secret boundary

Status: accepted

## Context

The existing environment boundary already prevented wholesale host-environment
inheritance and rejected common credential-bearing variable names. Step 132 tightens
that contract so an untrusted capability receives a small, structurally valid,
bounded environment before any sandbox/runtime control command is launched.

## Decision

The secret boundary now:

- permits only POSIX-safe environment variable names;
- rejects values that are not strings;
- rejects NUL, carriage-return, and newline characters;
- caps variable count, individual name size, individual value size, and aggregate value size;
- rejects common credential-bearing names and an optional explicit forbidden-name list;
- validates explicit caller-provided variables before copying them into the execution environment;
- produces bounded audit evidence containing counts and a deterministic fingerprint, but never
  stores or reports secret values.

The default limits are 64 variables, 255 bytes per name, 4096 bytes per value, and 64 KiB
total environment value bytes.

This remains an exclusion boundary, not a secret-management system. Capabilities that
need real secrets must be connected to a dedicated future secret broker/manager with
least-privilege access, short lifetimes, and auditable use.

## Rationale

Python's subprocess API uses the supplied env mapping instead of inheriting the current
process environment, making an explicit environment suitable as the runtime boundary.
OWASP guidance recommends minimizing plaintext secret exposure, avoiding routine
environment-variable handling where possible, and ensuring secrets are not written to
logs or audit streams.

## Validation

Focused unit coverage verifies sensitive-name rejection, invalid names and values,
resource bounds, explicit forbidden names, deterministic evidence, and the absence of
secret values from errors/evidence. Existing environment-isolation and runtime-audit
tests remain part of the full repository test suite.

## Limitations

The scanner intentionally does not attempt generic high-entropy or provider-specific
secret-value detection. Such heuristics can produce false positives and are not a
substitute for an explicit secret-management boundary. The compatible Apple Container
runtime still needs real Apple Silicon smoke validation beyond Linux-hosted CI.
