# `serving/` — Model Server Implementations

Concrete model server backends implementing the `IModelServer` interface. The platform supports multiple serving strategies — from a zero-dependency fake server for testing, through an in-process HuggingFace Transformers runtime, to remote OpenAI-compatible clients for vLLM and TGI.

---

## Architecture

```
IModelServer (interface)
  ├── FakeModelServer          (testing / placeholder)
  ├── HuggingFaceModelServer   (local in-process Transformers)
  └── OpenAICompatibleRemoteModelServer (remote HTTP client)
        ├── VLLMModelServer    (vLLM's OpenAI API)
        └── TGIModelServer     (TGI's Messages API)
```

---

## Files & Classes

### `factory.py` — `build_model_server`

Factory function that translates `ServingConfig.implementation` into a concrete `IModelServer`.

| Implementation Value | Backend Created | Description |
|---|---|---|
| `"fake"` | `FakeModelServer` | Deterministic stub for tests. |
| `"huggingface-transformers"`, `"transformers-local"` | `HuggingFaceModelServer` | Local in-process Transformers. |
| `"vllm"`, `"vllm-openai"` | `VLLMModelServer` | Remote vLLM HTTP client. |
| `"tgi"`, `"tgi-messages-api"` | `TGIModelServer` | Remote TGI HTTP client. |

---

### `fake_model_server.py` — `FakeModelServer`

Non-GPU serving stub for tests and placeholder flows. Returns deterministic responses without ML dependencies.

| Method | Signature | Use Case |
|---|---|---|
| `deploy` | `(model, request) → DeploymentRecord` | Creates a synthetic deployment record with placeholder metadata. |
| `unload` | `(deployment_id) → None` | No-op. |
| `health` | `() → dict` | Returns `{"status": "ok", "backend": "fake-model-server", "placements": ["cpu"]}`. |
| `generate` | `(deployment, request) → str` | Returns a deterministic placeholder response describing which deployment would have handled the request. |

---

### `huggingface_model_server.py` — `HuggingFaceModelServer`

In-process Transformers backend with placement-aware model loading. Suitable for local development, smoke tests, and CPU/MPS experimentation.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(config: ServingConfig)` | Store config, initialize deployment registry and threading lock. |
| `deploy` | `(model, request) → DeploymentRecord` | Resolves source model ID, negotiates placement (CPU/CUDA/MPS), downloads and loads tokenizer + model via `from_pretrained`, moves model to device, and stores the loaded deployment in memory. |
| `unload` | `(deployment_id) → None` | Removes the deployment from memory, triggers garbage collection, and clears GPU/MPS caches. |
| `health` | `() → dict` | Returns backend status and available placements detected from PyTorch. |
| `generate` | `(deployment, request) → str` | Applies the tokenizer's chat template, runs `model.generate()` with configured parameters, and decodes the completion tokens. Supports `enable_thinking` metadata for Qwen3 models. |
| `_resolve_source_model_id` | `(model, request) → str` | Internal — resolves the HuggingFace model identifier from request or model metadata. |
| `_resolve_torch_dtype` | `(torch_module, placement) → dtype` | Internal — selects `float32` for CPU, `float16` for GPU/MPS, or the explicitly configured dtype. |
| `_lazy_runtime_imports` | `() → _Runtime` | Internal — lazily imports `torch` and `transformers` so they're only loaded when the backend is actually used. |

---

### `openai_compatible_remote.py` — `OpenAICompatibleRemoteModelServer`

Base class for remote inference backends exposing an OpenAI-compatible chat completions API. Shared by vLLM and TGI clients.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(config: OpenAICompatibleBackendConfig)` | Store remote backend connectivity settings. |
| `deploy` | `(model, request) → DeploymentRecord` | Validates backend health, resolves base URL and remote model name, creates deployment record with remote metadata. |
| `unload` | `(deployment_id) → None` | No-op (remote servers are externally managed). |
| `health` | `() → dict` | Returns `"configured"` or `"unconfigured"` based on whether `base_url` is set. |
| `generate` | `(deployment, request) → str` | Sends a POST to the remote `/v1/chat/completions` endpoint, extracts `choices[0].message.content` from the response. |
| `_check_health` | `(base_url) → None` | Internal — sends a GET to the health endpoint to verify backend availability. |
| `_resolve_base_url` | `(request) → str` | Internal — resolves the API base URL from request metadata or config. |
| `_resolve_remote_model_name` | `(model, request) → str` | Internal — resolves the model identifier used by the remote API. |
| `_client` | `(base_url) → httpx.Client` | Internal — creates an authenticated HTTP client with timeout settings. |

---

### `vllm_client.py` — `VLLMModelServer`

Remote client for vLLM's OpenAI-compatible server. Inherits all behavior from `OpenAICompatibleRemoteModelServer` with `backend_name = "vllm-openai"`.

### `tgi_client.py` — `TGIModelServer`

Remote client for TGI's OpenAI-compatible Messages API. Inherits all behavior from `OpenAICompatibleRemoteModelServer` with `backend_name = "tgi-messages-api"`.

### `transformers_client.py`

Re-export alias for `HuggingFaceModelServer`. Exists to align the module layout with the implementation plan.

---

### `placement.py` — Execution Placement Resolution

Resolves where a model should run (CPU, CUDA, MPS) for local serving runtimes.

| Class / Function | Signature | Use Case |
|---|---|---|
| `PlacementAvailability` | Dataclass with `cpu`, `cuda`, `mps` booleans | Snapshot of which placements are available in the current process. |
| `PlacementAvailability.as_list` | `() → list[str]` | Returns available placements in deterministic order (cuda, mps, cpu). |
| `discover_placement_availability` | `() → PlacementAvailability` | Detects placement availability from the installed PyTorch runtime. Falls back to CPU-only if PyTorch is absent. |
| `resolve_placement` | `(preferred, fallbacks, availability) → str` | Resolves the first usable placement from preferred → fallbacks → CPU. Raises `ValueError` if nothing is available. |

---

### `docker_manager.py` — `DockerManager`

Manages Docker containers for vLLM serving. Reads configuration from `vllm_config.yaml`.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(config_path: str)` | Connects to Docker daemon via environment, loads serving config from YAML. |
| `start_vllm_server` | `() → Container \| None` | Launches a vLLM Docker container with GPU access, host networking, model cache volumes, and the configured model. Returns the container object or `None` on failure. |
