# ADR 0002: Deterministic Resource-Aware Admission

## Context

Super-Ai targets constrained local hardware and intends to load specialized capabilities only when needed. Modern on-device runtimes demonstrate explicit memory planning, while recent edge-agent research highlights dynamic memory/model-loading pressure during inference.

## Decision

Phase 0 uses a small deterministic admission controller before any worker is started.

A worker must declare a ResourceContract containing peak RAM, disk, CPU, and per-capability concurrency. The scheduler:

- keeps explicit system, control-plane, and safety RAM reservations;
- uses peak RAM for admission rather than average RAM;
- respects stricter per-task RAM, disk, and parallelism limits;
- reserves resources before execution and releases them after cleanup;
- rejects requests that do not fit instead of overcommitting;
- stays independent from OS telemetry so later telemetry can refresh ResourceSnapshot without redesigning capability contracts.

## Why this is important

Quantization can materially reduce model size, but model loading still consumes meaningful RAM. Shared allocators, memory arenas, memory-lifetime planning, and memory-aware scheduling therefore belong in the runtime architecture, not as afterthoughts.

## Future extension

Add a ResourceTelemetry provider that refreshes ResourceSnapshot at task boundaries and before admission. Later, the scheduler can incorporate GPU memory, thermal/power state, startup cost, cache residency, and measured peak usage while preserving the same contract interface.

## Research references

- ExecuTorch memory planning: https://docs.pytorch.org/executorch/stable/compiler-memory-planning.html
- ONNX Runtime allocator and arena behavior: https://onnxruntime.ai/docs/get-started/with-c.html
- 2026 edge-agent offloading research: https://www.sciencedirect.com/science/article/pii/S0167739X2600049X
- 2026 memory-aware edge runtime research: https://arxiv.org/abs/2608.10362
- llama.cpp model quantization documentation: https://github.com/ggml-org/llama.cpp
