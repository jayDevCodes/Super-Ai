# ADR 0036: Integrate environment isolation at the container boundary

## Status

Accepted.

## Context

Step 16 introduced a secret-safe execution environment, but AppleContainerExecutor also exposes a direct launch boundary. Relying only on an upstream controller leaves a bypass path where a caller could accidentally forward a sensitive host environment to the container CLI.

Python documents that passing an explicit `env` mapping to `subprocess` replaces the default inherited environment. citeturn887492search0 OWASP guidance also warns that secrets can be exposed through environment variables and recommends dedicated secret-management systems rather than routine environment-variable handling. citeturn887492search1turn887492search10

## Decision

Apply `build_sandbox_environment()` inside `AppleContainerExecutor.launch()` before any preflight, create, inspect, start, telemetry, or cleanup CLI operation.

This creates a defense-in-depth boundary: callers may supply only an explicit non-sensitive environment, and the executor never forwards an unvalidated mapping to the Apple Container CLI.

## Validation

Tests verify that sensitive environment names are rejected before any CLI call and that allowlisted/non-sensitive variables reach all container control operations while unrelated host variables such as `HOME` are omitted.

## Limitations

This remains a policy-level filter, not a complete secret-management system. Future steps should add a proper secret broker/vault boundary for capabilities that genuinely require secrets.