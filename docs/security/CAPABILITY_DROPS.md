# Capability drop and deny policy

Super-Ai treats Linux capability requests as an explicit allowlist contract.
There is no ambient capability inheritance and no silent “best effort” drop:

1. The runtime profile declares the exact allowlist.
2. A worker request is compared with that allowlist before launch.
3. Any missing capability rejects the request with a bounded error.
4. Administrative, tracing and wildcard capabilities are rejected while the
   boundary is constructed (`ALL`, `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, and
   `CAP_NET_ADMIN`).
5. The default profile requests no capabilities.

This means a specialist model cannot obtain extra host privileges merely because
its prompt or downloaded package asks for them. A future capability genuinely
requiring a privileged operation needs a separately reviewed, narrowly scoped
adapter and an updated evidence/test contract; it must not bypass this gate.

The control is intentionally independent of model selection. A smaller model
does not receive weaker isolation, and a larger model does not receive more
privilege. Capability admission occurs before the worker is loaded.
