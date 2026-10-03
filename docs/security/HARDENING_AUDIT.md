# Super-Ai hardening audit map

The hardening review is the admission boundary for a runtime security profile.
It produces a deterministic fingerprint, findings, and a named control set.
The fingerprint is evidence for correlation; it is not a substitute for the
runtime adapter's attestation.

## Controls

| ID | Boundary | Evidence / enforcement |
| --- | --- | --- |
| `non-root` | privilege | profile validation and runtime intent |
| `no-new-privileges` | privilege escalation | profile validation and runtime intent |
| `syscall-posture` | syscall surface | restricted posture contract |
| `filesystem-isolation` | writes | explicit absolute write roots |
| `network-policy` | egress | disabled-by-default or explicit allowlist |
| `secret-boundary` | environment | bounded explicit variables; no ambient secrets |
| `process-quota` | process count | bounded process rlimit |
| `open-file-quota` | descriptors | bounded file rlimit |
| `capability-boundary` | Linux capabilities | forbidden administrative capabilities rejected |
| `ownership-race-fence` | cleanup/replacement | exact ownership token and atomic handoff |

`HARDENING_CONTROL_IDS` is the single named list used by
`HardeningEvidence.control_ids`; adding or removing a control must update this
document and its evidence tests in the same change.

## Limits

The audit is deterministic policy evidence. It does not prove that a host
kernel, Apple Container runtime, GPU worker, or third-party model obeyed the
requested limits. Runtime creation and attestation remain mandatory before
execution; integration checks on compatible Apple Silicon are still required
for claims about Apple Container behavior.
