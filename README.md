# Super-Ai

Super-Ai is a modular personal-AI control plane designed for resource-constrained hosts. The repository acts as the durable brain/registry, while untrusted third-party capability code is intended to run only through a least-privilege runtime boundary.

## Current architecture

Task → Brain/DAG → Router/Policy → Resource Admission → Immutable Source Resolution → Staging → Workspace/Output Contracts → Runtime Admission → Sandbox → Execution → Verification → Cleanup → Audit/Telemetry.

The new control-plane layers added after step 31 are additive:
- core/controlplane: runtime-spec hardening and host-footprint configuration;
- core/supplychain: artifact identity, signatures, provenance, SBOM, dependency locks, revocation, mirrors, trust decisions, reconciliation and evidence;
- core/security: capability, syscall, filesystem, network, secret, process, quota and race-fence controls;
- core/runtime/admission.py: composed fail-closed admission;
- core/runtime/cleanup_guard.py: stale-cleanup race barrier.

## Resource target

The default configuration targets approximately 8 GB RAM and 256 GB storage with conservative concurrency and cache limits.

## Safety

Network access is denied by default at the security-posture layer. Third-party source identity is immutable and runtime image digests can be required. Secrets are excluded from the control-plane evidence model.

## Development

The project uses the standard library for the new control-plane modules. The existing GitHub Actions workflow runs the repository unit-test suite on Python 3.11, 3.12 and 3.13.

See docs/autonomy/ for the autonomous engineering protocol and docs/architecture/ for system contracts.

## Codex-style local workbench

The local UI is a conversation-first workbench with a task rail, composer,
animated guarded pipeline, model/resource inspector and live activity feed.
Start it with:

```bash
python3 ui/server.py
```

Then open <http://127.0.0.1:8787/>. The starter tasks and composer use the
read-only browser endpoint; the server returns the resource-aware catalog route
used by the inspector. The UI does not bypass policy, origin fencing or
confirmation gates.


## Browser task capability

Super-Ai includes a first-party `browser.agent` capability for controlled Chrome automation. It uses the official Playwright CLI, a dedicated persistent browser profile, explicit HTTPS origin allowlists, deterministic accessibility-tree interactions, bounded output, and confirmation gates for consequential actions.

Install it with:

```bash
bash scripts/install/browser-agent.sh
```

Create a task JSON using `docs/browser/GOOGLE_SESSION_SETUP.md`, then run:

```bash
python3 scripts/run_browser_task.py path/to/task.json
```

Add `--confirm` only when the task intentionally includes a consequential action.

Google credentials are never stored in the repository. Log in once to the dedicated profile manually and keep `.super-ai/browser/profile/` local.


For natural-language browser work, Super-Ai can manage the local planner model per task:

```bash
python3 scripts/run_browser_goal.py \
  "Open my Google-hosted app and inspect the current page" \
  --start-url https://example.google.com/ \
  --allowed-origin https://example.google.com \
  --allowed-origin https://accounts.google.com
```

Ollama-backed model routing uses task type plus RAM/disk budgets. Micro text work can use Gemma 3 270M, lightweight tool/function routing can use FunctionGemma 270M, normal text fallback can use SmolLM2 360M or Gemma 3 1B, low-RAM browser/vision work uses Qwen3.5 0.8B, normal browser work uses Qwen3.5 2B, and complex/visual work can escalate to Qwen3.5 4B. Phi-4-mini is available for mid-budget reasoning and coding. Pre-existing models now stay warm for a short configurable window (`SUPER_AI_OLLAMA_KEEP_ALIVE`, default `5m`) instead of being immediately unloaded, reducing repeated cold-start latency without downloading extra weights. Set it to `0` for immediate unload. Newly downloaded task-scoped models still follow the existing ephemeral deletion policy by default. See docs/research/SMALL_MODELS.md for the dated research snapshot and licensing notes.

For compact code repair, the catalog now has Qwen2.5-Coder 0.5B and 1.5B profiles. Optional embedding, speech, OCR, image and video workers are kept in a separate, resource-gated specialist catalog; they are not downloaded or activated merely by being listed. Run `python3 scripts/run_model_learning_demo.py` to exercise the routing lessons without downloading model weights. See [the multimodal runtime plan](docs/research/MULTIMODAL_RUNTIME.md) for the acceptance-test learning loop and safe quantization/sharding/offload strategy.

The [1,000-unit task catalog](docs/research/TASK_CATALOG_1000.md) maps each bounded unit to a current open-model/runtime candidate plus a verifier. It gives Super-Ai a stable evaluation surface for teaching routing and measuring regressions; `python3 scripts/run_task_catalog_demo.py` inspects representative units with no downloads.

The controller uses one browser action per planning cycle, obtains fresh accessibility refs after each action, and can request a selective screenshot for visual context rather than sending screenshots on every cycle. Browser planning also defaults to a bounded 32K working context and 384 generated tokens, while retaining Ollama structured outputs and `think=false`; this keeps ordinary action-selection cycles fast and predictable. Consequential external effects still stop for confirmation.


## Owner final-decision authorization

Super-Ai has a local owner-only policy exception path for cases where the current task conflicts with an existing policy and the human intentionally wants to make the final decision.

Configure it once:

```bash
python3 scripts/setup_owner_auth.py
```

The setup tool accepts the code only from an interactive hidden prompt. It rejects non-interactive input so the code is not accidentally supplied through a pipe or shell argument. Only a salted scrypt verifier is stored under `.super-ai/security/owner_auth.json`; the code itself is not stored or sent to models. The verifier directory is restricted to the owner, and the verifier is written atomically with restrictive file permissions. If a verifier already exists, rotation requires an explicit `--rotate` confirmation. Never place the owner code in commands, environment variables, Git files, logs, prompts, or task output.

During a policy conflict, application code can call `Brain.execute(..., owner_override_code=...)`. The code is checked against the local verifier, converted into a short-lived task-scoped grant, consumed once, and recorded in the append-only audit hash chain with task/capability/policy evidence. The code never enters model context.

The owner decision can override the policy-engine decision for that specific task, but primitive safety boundaries such as secret handling, path traversal protection, arbitrary planner code execution, and explicit browser origin fencing remain enforced in the deterministic execution layer.
