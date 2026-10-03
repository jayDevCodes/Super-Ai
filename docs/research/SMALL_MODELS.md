# Small local model research

Research snapshot: 2026-10-03

Super-Ai should optimize for reliable work per unit of RAM and disk, not one
large model that stays resident. The catalog therefore routes small, bounded
tasks to a smaller model and reserves multimodal/reasoning models for tasks
that actually need them. Models are pulled only inside `TaskModelManager`'s
task-scoped lifecycle and are unloaded after each task.

## Current candidates

| Ollama model | Ollama size | Context | Input | License | Super-Ai role |
| --- | ---: | ---: | --- | --- | --- |
| `gemma3:270m` | 292 MB | 32K | text | Gemma terms | micro classification, extraction, short labels |
| `smollm2:360m` | 726 MB | 8K | text | Apache-2.0 | compact text fallback for extraction/classification |
| `gemma3:1b` | 815 MB | 32K | text | Gemma terms | short summaries and general text tasks |
| `qwen3.5:0.8b` | 1.0 GB | 256K | text + image | Apache-2.0 | low-RAM browser and visual fallback |
| `qwen3.5:2b-q4_K_M` | 1.9 GB | 256K | text + image | Apache-2.0 | normal browser/extraction work |
| `phi4-mini:3.8b-q4_K_M` | 2.5 GB | 128K | text | MIT | mid-budget reasoning, coding, tool-oriented tasks |
| `qwen3.5:4b-q4_K_M` | 3.4 GB | 256K | text + image | Apache-2.0 | complex browser, vision and reasoning tasks |

The size and context values above are the published Ollama artifacts, not a
promise of peak process RSS. Runtime admission still uses conservative RAM
estimates and measured feedback before increasing concurrency.

## Routing policy

1. A micro text task selects `gemma3:270m` when its budget allows it.
2. A normal browser task selects Qwen3.5 2B; a tight browser budget falls
   back to Qwen3.5 0.8B rather than using a text-only model.
3. A visual task requires a catalog model with `supports_vision=True`.
4. Complex/visual browser work can escalate to Qwen3.5 4B; the 4B model is
   never downloaded for a short extraction task.
5. Gemma models are open-weight candidates under Google's Gemma terms; they
   are not treated as Apache/MIT-licensed models.

## Primary sources

- Qwen3.5 Ollama library and tags: https://ollama.com/library/qwen3.5
- Qwen3.5 4B Q4_K_M details: https://ollama.com/library/qwen3.5:4b-q4_K_M
- Gemma 3 Ollama library: https://ollama.com/library/gemma3
- SmolLM2 Ollama library: https://ollama.com/library/smollm2
- Phi-4-mini Ollama library: https://ollama.com/library/phi4-mini
- Qwen3.5 0.8B model card/license: https://huggingface.co/Qwen/Qwen3.5-0.8B
- Gemma 3 270M model card/terms: https://huggingface.co/google/gemma-3-270m-it
- SmolLM2 360M model card/license: https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct

Before promoting a newer model, Super-Ai should check its official model
card, license, Ollama tag availability, structured-output reliability and
measured RAM/latency on the target machine.
