# Agent Handoff Contract

Read this file and CURRENT_CONTEXT.md before changing Super-Ai.

## First action on every step
1. Read docs/autonomy/state.json.
2. Read this continuity folder.
3. Audit open autonomous PRs.
4. Audit recent main CI and older failures that could still indicate a regression.
5. Compare the proposed step with existing contracts and tests.

## How to carry forward prior agents' work
Treat existing code, ADRs, tests, benchmarks, failure repairs, and research notes as accumulated engineering knowledge. Do not discard a design simply because a new agent would implement it differently. Change it only when current evidence shows a concrete defect, incompatibility, security issue, or materially better contract.

Before replacing a component, write down:
- what the existing component guarantees;
- which callers/tests depend on it;
- why the new design preserves or intentionally changes those guarantees;
- how migration/compatibility is handled.

## Continuity update after every completed step
Update CURRENT_CONTEXT.md with the new architecture/state and append one dated entry to JOURNAL.md containing:
- step number and title;
- branch/PR/merge commit;
- research sources or version assumptions;
- important design decision;
- tests/CI result;
- any failure and its repair;
- remaining limitations or follow-up dependencies.

Then update docs/autonomy/state.json and the roadmap checkpoint only after the implementation is validated and merged.

## Knowledge boundaries
Persist facts, interfaces, invariants, decisions, test evidence, failure lessons, and concise rationale. Do not persist private chain-of-thought, secrets, credentials, personal data, or unverified claims.

## Agent-to-agent principle
The next agent should be able to resume from the repository alone: source code + tests + ADRs + roadmap/state + .super-ai/continuity. It should not depend on a missing chat session or on one agent remembering an undocumented decision.

## Stop conditions
Pause for user input only for credentials/secrets, consequential external actions, destructive actions outside the controlled repository/workspace, or genuinely ambiguous irreversible requirements.

## Ordering rule
Never skip a failing regression to reach a new feature. Research the failure, repair it, validate, and only then advance.