# Decision 0046 — Supply-chain graduation

Status: accepted

An artifact is eligible for third-party execution only after immutable identity and the
configured evidence policy pass. ArtifactStore is an admission boundary, not a downloader
or executor. Mirror selection and registry reconciliation stay pure and deterministic.
