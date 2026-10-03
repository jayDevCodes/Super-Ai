# Network policy

Super-Ai networking is deny-by-default at both the security profile and the
browser boundary. A worker receives network access only through an explicit
allowlist:

- URL access accepts HTTPS only and compares the parsed hostname against the
  case-insensitive host allowlist.
- Direct IP access is checked against explicit CIDR ranges.
- Credentials, whitespace/control characters and malformed host/CIDR entries
  are rejected during validation.
- A browser task separately supplies an origin allowlist; that boundary is not
  widened by a model-generated URL or a prompt.

The control plane compiles the policy into runtime intent, but a runtime
adapter must still enforce and attest it. If the adapter cannot provide the
requested network mode, execution fails closed. Network policy is independent
of model selection and cannot be relaxed for image/video downloads or remote
planner convenience.
