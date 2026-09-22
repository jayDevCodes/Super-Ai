# CI Failure Repair Pipeline

## Goal

Keep CI repair strictly sequential. A failure becomes an engineering issue only after its
first/root exception is identified. Cascading test failures caused by the same root exception
are grouped into one queue item.

## Pipeline

1. Collect the latest failed "Super-Ai tests" workflow and preserve the raw log.
2. Normalize timestamps/ANSI noise and extract failed test names plus root exception signatures.
3. Collapse identical root exception signatures into one repair issue.
4. Select exactly one unresolved issue, in first-observed order.
5. Research line-by-line: failing log context, current implementation, relevant tests, recent commits,
   and the contract the failure is supposed to protect.
6. Reproduce the smallest relevant test first.
7. Patch minimally while preserving security/fail-closed behavior.
8. Verify the current issue with targeted tests, then the full CI matrix.
9. Only after that verification succeeds, mark the issue resolved and advance to the next issue.
10. After the queue is empty, require a green main-branch CI run before declaring repair complete.

## No-prompt rule

The repair agent continues to the next queue item automatically after successful verification. Routine
CI failures do not require a user message saying "next".

The agent stops only when evidence is insufficient, external credentials/hardware are required, a
proposed fix would weaken a security boundary, or the current issue remains failing after bounded repair.

A cancelled CI job is not successful verification.

## Security rules

Never weaken sandboxing, secret boundaries, ownership fences, verification gates, or network defaults
just to make CI green. Tie every resolved issue to a concrete repair commit and a green verification run.

## Local tooling

    python scripts/ci_failure_repair_queue.py --input ci-failed.log --output ci-failure-repair-queue.json

The workflow .github/workflows/ci-failure-repair-queue.yml performs this triage automatically when
"Super-Ai tests" fails and uploads both the raw log and ordered queue as an artifact.
