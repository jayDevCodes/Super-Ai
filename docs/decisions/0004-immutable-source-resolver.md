# ADR 0004: Immutable GitHub Source Resolver

## Context

Super-Ai must keep many capabilities available in GitHub without keeping every implementation locally. The runtime therefore needs a deterministic way to translate a capability manifest into an exact source revision and a minimal checkout plan.

## Decision

Add a GitHubSourceResolver that:

- accepts only validated HTTPS github.com repository URLs;
- requires an immutable 40-character Git commit SHA;
- produces an archive URL pinned to that commit;
- produces a shallow, blob-filtered Git clone plan;
- produces a sparse-checkout plan for a declared subdirectory;
- never downloads or executes source itself.

This separates source identity/planning from network access, artifact verification, sandboxing, and execution.

## Why this supports the 8 GB / 256 GB goal

A capability can be selected from metadata and staged only when needed. A blob-filtered shallow clone plus sparse checkout can reduce unnecessary object and working-tree materialization when the capability only needs a small repository portion. Actual savings depend on repository structure and Git/server support, so benchmarks remain mandatory.

## Security invariant

The resolver never accepts a moving branch/tag as the source identity. The execution plan is tied to the exact commit SHA stored in the manifest.

## Next step

Implement the network/artifact staging boundary that executes this plan with:

- HTTPS only;
- pinned commit verification;
- checksum verification when an artifact checksum is declared;
- sandboxing;
- CPU/RAM/disk/time limits;
- bounded cleanup.
