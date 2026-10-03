# ADR 0052 — Natural-Language Browser Control Loop

## Status

Accepted as an additive extension of ADR 0051.

## Decision

Add a closed-loop natural-language browser controller:

`user goal -> observe -> plan one action -> policy/validation -> execute -> re-observe -> verify -> repeat`.

The planner produces structured JSON through Ollama's `/api/chat` endpoint. The output is constrained by a JSON Schema, parsed into the existing `BrowserAction` contract, and validated before execution.

## Why one action per planning cycle

Playwright's coding-agent CLI returns an accessibility snapshot after commands and documents that refs should be re-snapshotted after navigation/state changes because refs are invalidated. The controller therefore executes one planned action, then obtains a fresh URL and snapshot before asking the model for the next action.

## Planner boundary

The default implementation is `OllamaBrowserIntentPlanner`, but the Brain may inject a task-selected model.

- Local endpoint by default: `http://127.0.0.1:11434`.
- Task model selection is handled by `core.models.TaskModelManager`.
- The managed catalog prefers the smallest viable Qwen3.5 model under the task's RAM/disk budget, accounting for the browser capability footprint.
- An already-installed model is reused without a redundant pull; a model downloaded for an ephemeral task is unloaded from RAM and removed after the task.
- `SUPER_AI_BROWSER_MODEL` / explicit model selection can override automatic selection when the requested model is in the managed catalog.
- Structured JSON output is enforced with a JSON Schema.
- Thinking is disabled for the short tool-planning step to reduce latency.
- Page content is explicitly treated as untrusted data to reduce prompt-injection risk.
- The model never receives a credential store or host environment.

## Verification

The model may provide text and URL post-conditions, but the controller verifies them deterministically against the observed page and current URL. A model completion claim without grounded evidence is rejected.

For visual-only UI state, the planner can request one screenshot action; the next planning cycle receives that screenshot as multimodal input while still using the fresh accessibility tree as the interaction source.

## Consequential actions

The planner must mark irreversible or externally consequential operations as consequential and request confirmation. A second deterministic keyword guard also flags common high-impact verbs in the user goal. Approval is supplied by an interactive callback or by a trusted higher-level workflow.

## Human authentication

Authentication remains outside the planner. The user logs into a dedicated persistent Chrome profile manually. Browser automation reuses that profile; no passwords, cookies, tokens, or storage-state files are written to Git.

## Resource rationale

Current Ollama Qwen3.5 tags include 0.8B, 2B Q4_K_M (~1.9 GB), and 4B Q4_K_M (~3.4 GB) text+image variants. The task model manager chooses among these according to task type and resource budgets, rather than keeping a large model permanently resident. This makes the browser path compatible with the repository's constrained-host design while still allowing a larger model when the task budget leaves sufficient headroom.

## Non-goals

This ADR does not add CAPTCHA bypass, 2FA bypass, arbitrary `eval` planning, unrestricted navigation, background unattended payments, or automatic submission of consequential forms.

## References

- Playwright coding-agent CLI introduction and quick-start documentation.
- Playwright snapshot/refs guidance.
- Playwright session/profile documentation.
- Ollama structured-output documentation.
- Ollama Qwen3.5 model registry.
