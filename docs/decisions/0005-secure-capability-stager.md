# ADR 0005: Secure Capability Stager

## Context

The registry resolver creates an immutable GitHub source plan, but it must not become a code-execution component. Super-Ai needs a bounded staging boundary that can retrieve a capability source, verify its artifact identity, and materialize it into an ephemeral workspace without allowing archive metadata to escape that workspace.

## Decision

Add a CapabilityStager that:

- accepts only a plan regenerated from the validated capability manifest;
- downloads only over HTTPS from GitHub archive hosts;
- bounds compressed download size, extracted size, archive member count, and download time;
- verifies SHA-256 when the manifest declares one, while always calculating the archive digest for diagnostics;
- extracts tar archives manually instead of using unrestricted extraction;
- rejects absolute paths, parent-directory traversal, symlinks, hardlinks, and special filesystem entries;
- requires exactly one top-level repository directory;
- removes the compressed archive after staging;
- removes the partially staged source on any failure;
- never imports, installs, or executes staged code.

OS-level sandbox execution is intentionally not implemented by this component. It remains a separate runtime boundary so source retrieval and execution cannot silently share trust assumptions.

## Resource rationale

The default limits are intentionally small for an 8 GB / 256 GB target: 64 MB compressed source, 256 MB extracted source, and 20,000 archive members. These are policy defaults rather than hardware guarantees; capability-specific limits and benchmarks can tune them later.

## Security invariant

A staged capability is never selected from a moving branch or tag. The stager recomputes the source plan from the manifest and refuses a tampered or mismatched plan before network access.
