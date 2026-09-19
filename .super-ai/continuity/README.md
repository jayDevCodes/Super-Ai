# Super-Ai Persistent Agent Memory

This dot-folder is the durable handoff layer for the 1000-step engineering program.

Purpose:
- preserve architecture decisions, invariants, failure lessons, research assumptions, and next-step context across agent/session changes;
- prevent prior engineering work from being forgotten or re-derived unnecessarily;
- keep an append-only trail of what changed, why it changed, and what remains.

Important boundary:
This folder stores structured engineering context and decision summaries. It must not contain credentials, API keys, tokens, private user data, or private chain-of-thought. When deeper reasoning is needed, the next agent should re-derive it from the recorded facts, tests, source code, and research references.

Files:
- CURRENT_CONTEXT.md — latest architecture and runtime state snapshot.
- AGENT_HANDOFF.md — instructions for the next engineering agent.
- JOURNAL.md — append-only continuity log.

Update rule:
Every completed step must update CURRENT_CONTEXT.md and append a compact entry to JOURNAL.md before the autonomous checkpoint is advanced. Never delete historical entries merely to make the snapshot shorter.

Visibility:
A leading-dot directory is visually hidden in some local file browsers, but it is still part of Git history and is not a secret vault.