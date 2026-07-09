# `gateway/` — HTTP API Gateway

FastAPI-based HTTP gateway exposing the platform's model management, chat completion, health, and metrics endpoints. Supports both a native platform API and an OpenAI-compatible `/v1/` prefix.

---

## Files & Classes

### `app.py` — Application Factory

| Function | Signature | Use Case |
|---|---|---|
| `create_app` | `(platform_application: PlatformApplication) → FastAPI` | Creates a FastAPI app, pins the `PlatformApplication` container into `app.state`, and mounts all routers. |
| `create_default_app` | `() → FastAPI` | Convenience factory that builds the default app from `configs/platform.yaml`. Suitable for `uvicorn` entrypoints. |

---

### `dependencies.py` — Dependency Injection Helpers

FastAPI `Depends()` functions that retrieve services from the application state.

| Function | Signature | Use Case |
|---|---|---|
| `get_application` | `(request: Request) → PlatformApplication` | Retrieves the `PlatformApplication` container from `request.app.state`. Used by all route handlers to access services without re-initialization. |
| `get_chat_service` | `(request: Request, app_state: PlatformApplication) → ChatService` | Constructs a `ChatService` instance with a `VllmModelServer` using the current configuration. Used for the async chat completion endpoint. |

---

### `routes.py` — Route Definitions

Defines two routers: `router` (root prefix) and `v1_router` (`/v1` prefix for OpenAI compatibility).

#### Internal Helper

| Function | Signature | Use Case |
|---|---|---|
| `_translate_error` | `(error: PlatformError) → HTTPException` | Maps platform exceptions (`NotFoundError`, `RoutingError`, `ValidationError`) to appropriate HTTP status codes (404, 400, 500). |

#### Chat Completion Endpoints

| Endpoint | Method | Route | Response Model | Description |
|---|---|---|---|---|
| `create_chat_completion` | POST | `/chat/completions` | `ChatCompletionResponse` | Native platform chat completion with routing metadata. |
| `create_openai_chat_completion` | POST | `/v1/chat/completions` | `OpenAIChatCompletionResponse` | OpenAI-compatible chat completion that wraps the response in `choices[]` format. |

#### Model Management Endpoints

| Endpoint | Method | Route | Response Model | Description |
|---|---|---|---|---|
| `register_model` | POST | `/models/register` | `ModelResponse` (201) | Register a new model in the platform registry. |
| `deploy_model` | POST | `/models/deploy` | `DeploymentResponse` (201) | Deploy a registered model through the configured serving backend. |
| `unload_model` | POST | `/models/unload` | `DeploymentResponse` | Unload an active deployment. |
| `validate_model` | POST | `/models/validate` | `ValidationResponse` | Inspect a HuggingFace repo and return a compatibility report. |
| `list_models` | GET | `/models` | `ModelsResponse` | List all registered models. |
| `get_model` | GET | `/models/{model_id}` | `ModelResponse` | Get a single model by ID. |
| `get_model_status_v1` | GET | `/v1/models/{model_id}/status` | `ModelResponse` | Model status endpoint (v1 alias). |

#### Health & Metrics Endpoints

| Endpoint | Method | Route | Description |
|---|---|---|---|
| `get_health` | GET | `/health` | Returns serving backend health and aggregate telemetry metrics. |
| `get_metrics` | GET | `/metrics` | Returns telemetry snapshot (total requests, errors, average latency). |

> **Note:** All model management and chat endpoints are also mirrored under the `/v1/` prefix for OpenAI-compatible tooling.
