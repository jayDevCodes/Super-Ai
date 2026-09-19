# Decision 0041 — Supply-chain admission

Status: accepted

Autonomous third-party capability execution now has an additive supply-chain evidence
model. Artifact identity, signatures, provenance, SBOM summaries, dependency locks,
revocation entries, deterministic trust scoring, and registry reconciliation are all
represented independently.

The trust score is only an admission heuristic over available evidence. It is not
presented as a cryptographic security guarantee. The default policy requires all
four
evidence classes, blocks critical vulnerabilities, and rejects revoked identities.
