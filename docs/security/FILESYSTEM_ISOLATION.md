# Filesystem isolation

The default worker filesystem is a read-only root with two explicit write
roots: `/workspace` for task artifacts and `/tmp` for bounded scratch data.
The security profile validates absolute paths, rejects control characters and
rejects `..` traversal segments before runtime translation.

The control plane emits deterministic write-root intent and the runtime adapter
must mount/attest only those roots. A model, downloaded package or browser
task cannot expand the write scope through prompt text. A task that needs a
different workspace must receive a new reviewed profile; it must not mutate the
global default.

This contract limits path scope but does not replace output verification,
ownership-checked cleanup or a host filesystem policy. The adapter must fail
closed if it cannot provide a read-only root or the requested write roots.
