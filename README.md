# Foundation AI Platform

Production-grade, configuration-driven LLM platform skeleton for hosting and routing multiple model backends through a unified internal API.

## Goals

- Python 3.12+
- Configuration-driven behavior through YAML and environment overrides
- Plugin-driven model family integration
- Fully testable without GPU access
- Stable interfaces between subsystems
- Documentation-first repository structure

## Repository Layout

- `llm_platform/`: core Python package
- `configs/`: YAML configuration examples and defaults
- `docs/`: architecture and operational design documents
- `tests/`: unit, integration, and end-to-end test suites
- `scripts/`: operator and developer scripts
- `deployment/`: deployment assets and environment templates

## Delivery Phases

1. Phase 0: architecture, interfaces, schemas, configuration, tests, docs
2. Phase 1: registry skeleton
3. Phase 2: plugin framework skeleton
4. Phase 3: lifecycle management skeleton
5. Phase 4: routing skeleton
6. Phase 5: gateway skeleton
7. Phase 6: telemetry skeleton

## Current Status

This repository currently provides a production-oriented scaffold and placeholder implementations intended to evolve into a full internal AI platform without locking the design to any specific model family or serving engine.

It now also includes:

- a placement-aware local HuggingFace Transformers backend for `cpu`, `mps`, and `cuda`
- Alembic-managed SQLite persistence by default
- a smoke-test script for a real local model-hosting path
- a native Apple Silicon serving path in [`mac-serving`](mac-serving/README.md)
  for Gemma 4 E4B GGUF models using llama.cpp's Metal backend, with an
  OpenAI-compatible endpoint, lifecycle controls, health and metrics endpoints,
  footprint planning, and benchmarking tools
