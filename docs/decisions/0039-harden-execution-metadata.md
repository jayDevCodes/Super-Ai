# ADR 0039: Harden Execution Metadata

## Status

Accepted — step 31.

## Decision

Harden `ExecutionResult.as_metadata()` as a strict control-plane projection.

The projection now:

- carries an explicit schema version;
- excludes stdout, stderr, and raw telemetry;
- sanitizes control characters from cancellation text;
- bounds cancellation text and output-path/violation strings;
- caps metadata lists at 32 items;
- normalizes negative counters to zero;
- rejects non-finite durations by representing them as null;
- accepts only a validated sha256 digest shape for image identity.

The implementation also preserves the output inspection evidence needed for verification without exposing unbounded filesystem details.

## Research basis

OWASP recommends that sensitive values such as access tokens, passwords, keys, and other sensitive data not be written directly to logs, and recommends sanitizing dangerous characters before logging. citeturn568859search0turn568859search1

OpenTelemetry's current specification recommends limits on attribute count and value length so erroneous or untrusted attributes cannot exhaust memory or overwhelm telemetry pipelines. citeturn568859search2turn568859search3

OpenTelemetry also recommends data minimization and removing or transforming sensitive telemetry data before export. citeturn568859search4

## Consequences

Positive:

- metadata is bounded before it reaches audit/telemetry consumers.
- log-injection risk from control characters is reduced.
- malformed numeric and digest values do not propagate as trusted control-plane facts.

Trade-off:

- some diagnostic detail is intentionally truncated or discarded.
- downstream consumers must tolerate the new metadata schema version and nullable normalized fields.
