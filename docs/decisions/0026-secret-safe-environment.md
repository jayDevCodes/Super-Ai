# ADR 0026: Secret-Safe Sandbox Environment

## Status

Accepted.

## Decision

Never forward the host process environment wholesale to capability execution.

Sandbox environments inherit only an explicit small allowlist such as `PATH`, `LANG`, and `LC_ALL`, plus explicit non-sensitive variables supplied by the caller. Names containing common credential/secret indicators are rejected. Values are bounded and control characters are rejected.

This reflects current secret-management guidance: environment variables can expose secrets broadly and can appear in logs or dumps, so they should not be the default secret transport. citeturn281030search3

GitHub's secret-scanning/push-protection features remain an additional repository-level control; they are not a substitute for runtime secret isolation. citeturn281030search0turn281030search7

## Consequences

Capability execution has a much smaller ambient environment and is less likely to accidentally inherit developer credentials or CI secrets.
