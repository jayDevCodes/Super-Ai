# Security posture controls

Security controls are represented as immutable, auditable policy objects. The default
profile is non-root, no-new-privileges, restricted syscall posture, read-only root
filesystem, explicit write roots, deny-by-default network access, bounded process/file
quotas, and no ambient secrets.

The secret boundary is enforced before sandbox launch: only explicit bounded environment
variables are accepted, common credential-bearing names are denied, invalid environment
names/values are rejected, and aggregate environment size is capped. Secret values are
never included in scan findings or audit evidence. Capabilities that genuinely require a
secret are expected to use a future dedicated secret-management boundary rather than
forwarding ambient host credentials.

The translation layer emits deterministic intent for a runtime adapter; it does not
directly launch containers.
