# Security posture controls

Security controls are represented as immutable, auditable policy objects. The default
profile is non-root, no-new-privileges, restricted syscall posture, read-only root
filesystem, explicit write roots, deny-by-default network access, bounded process/file
quotas, and no ambient secrets.

The translation layer emits deterministic intent for a runtime adapter; it does not
directly launch containers.
