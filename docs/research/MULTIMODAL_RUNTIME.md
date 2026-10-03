# Multimodal specialist runtime

Research snapshot: 2026-10-03. This is a conservative deployment plan, not a
claim that every model below is installed or suitable for every machine.

## Capability map

| Need | Candidate | Default deployment | Admission rule |
| --- | --- | --- | --- |
| Small code repair | Qwen2.5-Coder 0.5B / 1.5B | Ollama task-scoped model | RAM/disk budget and code-repair acceptance case pass |
| Retrieval memory | BGE-small-en-v1.5 | CPU embedding worker | output dimension, normalized-vector and retrieval tests pass |
| Speech to text | Whisper tiny | CPU worker | short audio transcription fixture passes |
| OCR | PP-OCR mobile tier | CPU worker | image-to-text fixture passes with bounded output |
| Image generation | SD-Turbo | optional accelerator worker | GPU/VRAM admission plus image artifact verifier |
| Video generation | Wan2.1-T2V-1.3B | optional accelerator worker | GPU/VRAM admission, duration/resolution cap, artifact verifier |
| Browser automation | local planner plus deterministic browser capability | task-scoped planner | origin allowlist, confirmation and browser fixtures pass |

`core.models.SpecialistModelRegistry` contains the resource gate for these
workers. It registers metadata only: it never downloads a model, enables a
remote endpoint, or grants a capability new permissions.

## Teaching loop

Super-Ai should learn operationally, not silently alter its own policies or
weights:

1. Add a small representative task with an expected route and verifier.
2. Run it with a constrained budget and retain route, runtime and outcome
   telemetry.
3. Promote a model/capability only after the acceptance case succeeds.
4. Keep a regression case; demote it when failures recur.
5. Tune resource recommendations from measured runs using the existing
   `ResourceFeedbackController`; do not auto-change safety policy.

`python3 scripts/run_model_learning_demo.py` runs four routing lessons and an
embedding-worker selection locally. It is deterministic and downloads no
weights. It is the first smoke lesson to run before a real specialist is
installed.

## Large-model storage and loading

Never split raw model bytes at arbitrary offsets and try to independently run
the pieces. Use the format/runtime's supported mechanism instead:

- **Quantized single artifact:** GGUF/MLX/4-bit weights for task-scoped local
  LLMs, with an exact upstream revision and digest recorded.
- **Official shards:** safetensors shards remain a single checkpoint manifest;
  fetch and verify each shard through the supply-chain store.
- **Offload:** retain inactive components on CPU/disk and move supported layers
  to the accelerator only during inference. This lowers VRAM but can be slow.
- **Adapters:** keep LoRA/adapters separate from immutable base weights, record
  both identities, and load them only for the matching task.

Image and video must remain opt-in accelerator workers. SD-Turbo's official
repository is roughly 13 GB, and current Diffusers guidance notes that modern
diffusion pipelines can need much more memory than their nominal parameter
count because activation/denoising memory is substantial. CPU/disk offload is
allowed only when a task accepts the speed trade-off. Video has a strict
duration/resolution budget so one request cannot monopolize the host.

## Sources

- Qwen2.5-Coder: <https://ollama.com/library/qwen2.5-coder>
- BGE-small-en-v1.5: <https://huggingface.co/BAAI/bge-small-en-v1.5>
- Whisper: <https://github.com/openai/whisper/blob/main/model-card.md>
- PaddleOCR: <https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md>
- SD-Turbo: <https://huggingface.co/stabilityai/sd-turbo>
- Wan2.1-T2V-1.3B: <https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B>
- Diffusers offload guidance: <https://huggingface.co/docs/diffusers/en/quicktour>
