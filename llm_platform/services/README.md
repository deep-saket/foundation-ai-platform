# `services/` — Application Service Layer

Orchestration services that coordinate registry lookups, routing, lifecycle updates, serving backend invocation, and telemetry emission. These services are the primary entry points for business logic and are intentionally transport-agnostic — they receive and return Pydantic models, not HTTP objects.

---

## Files & Classes

### `chat.py` — `ChatService`

Main orchestration entrypoint for chat completions. Coordinates routing, lifecycle touch, model-server invocation, and telemetry.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(registry: IRegistry, router: IRouter, lifecycle_manager: ILifecycleManager, telemetry_provider: ITelemetryProvider, model_server: IModelServer)` | Inject all dependencies required for the chat completion workflow. |
| `create_completion` | `(request: ChatCompletionRequest) → ChatCompletionResponse` | **Full chat flow:** (1) list models and deployments from registry, (2) resolve preferred model if specified, (3) route to eligible deployment via `CapabilityRouter`, (4) touch lifecycle to reset idle timer, (5) call `model_server.generate()` for inference, (6) emit telemetry event with latency, (7) return response with routing metadata and generated message. |
| `_resolve_requested_model_id` | `(request: ChatCompletionRequest, models) → str \| None` | Internal — resolves `request.model` by matching against model IDs or names. Raises `NotFoundError` if the specified model is not in the registry. |

---

### `model_management.py` — `ModelManagementService`

Coordinates model registration, deployment through serving backends, and unloading workflows.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(registry: IRegistry, model_server: IModelServer, compatibility_checker: ICompatibilityChecker, lifecycle_manager: ILifecycleManager)` | Inject dependencies for the model management workflow. |
| `register_model` | `(request: ModelRegistrationRequest) → ModelRecord` | Validate model metadata via compatibility checker, then persist through the registry. |
| `deploy_model` | `(request: DeploymentCreateRequest) → DeploymentRecord` | **Full deploy flow:** (1) fetch model from registry, (2) validate deployment via compatibility checker, (3) deploy through model server, (4) mark deployment as `READY`, (5) initialize lifecycle state to `HOT`, (6) update model status to `DEPLOYED`. |
| `unload_model` | `(deployment_id: str) → DeploymentRecord` | Fetch the deployment, call `model_server.unload()`, and mark the deployment as `UNLOADED`. |
| `list_models` | `() → list[ModelRecord]` | List all registered models (delegates to registry). |
| `get_model` | `(model_id: str) → ModelRecord` | Get a single registered model by ID (delegates to registry). |

---

### `health.py` — `HealthService`

Exposes lightweight health and metrics summaries.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(model_server: IModelServer, telemetry_provider: ITelemetryProvider)` | Inject model server and telemetry dependencies. |
| `health` | `() → dict[str, object]` | Returns a dictionary with `status: "ok"`, serving backend health, and aggregate telemetry metrics snapshot. Used by `GET /health`. |

---

### `model_server.py` — `VllmModelServer`

A work-in-progress concrete `IModelServer` implementation that communicates directly with a running vLLM container over HTTP.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `()` | Initialize the vLLM server client (base URL from config, currently stubbed). |
| `generate` | `(deployment: object, request: ChatCompletionRequest) → str` | **Async** — sends a POST request to the vLLM container's `/v1/chat/completions` endpoint with the message payload, and extracts the natural language response from the JSON result. |

> **Note:** This class is a development prototype. The production vLLM client is in `serving/vllm_client.py`.
