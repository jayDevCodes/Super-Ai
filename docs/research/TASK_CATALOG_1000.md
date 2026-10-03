# 1,000-unit Super-Ai task catalog

The live catalog is generated in `core.models.task_catalog` as a stable 10 ×
10 × 10 matrix: 10 domains, 10 workflow phases and 10 operational conditions.
This creates exactly 1,000 independently named task units without maintaining a
fragile manually duplicated list.

Every unit includes:

- a runtime and best currently admitted open model;
- an explicit verifier type;
- a build path that requires a fixture before promotion.

| Domain | Units | Current primary worker |
| --- | ---: | --- |
| Text | 100 | Gemma 3 270M |
| Classification | 100 | SmolLM2 360M |
| Reasoning | 100 | Phi-4-mini Q4 |
| Code | 100 | Qwen2.5-Coder 1.5B |
| Browser | 100 | Qwen3.5 2B + deterministic browser agent |
| Vision | 100 | Qwen3.5 4B |
| Retrieval | 100 | BGE-small-en-v1.5 |
| Speech | 100 | Whisper tiny |
| Image | 100 | SD-Turbo (accelerator-gated) |
| Video | 100 | Wan2.1 T2V 1.3B (accelerator-gated) |

Run `python3 scripts/run_task_catalog_demo.py` to make Super-Ai inspect a
representative set. It performs no download or model inference.

“Best” is a current constrained-host routing choice—not an unqualified quality
claim. A worker can only become eligible after its own fixture and verifier
pass. For a missing capability, implement the deterministic executor and
verifier first, then evaluate an open model; do not train or publish a model
without a dataset, license review, reproducible recipe, safety review and
benchmark evidence.
