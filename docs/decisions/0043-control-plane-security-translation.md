# Decision 0043 — Security control translation

Status: accepted

Security posture is represented as immutable policy and translated into deterministic
runtime intent. The control plane does not call a container runtime directly from the
translation layer. This preserves a least-privilege boundary and lets the existing
Apple Container executor remain the only runtime-specific adapter.
