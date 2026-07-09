# `interfaces/` — Abstract Contracts

Defines the abstract base classes (ABCs) that every swappable platform component must implement. The rest of the codebase depends on these interfaces rather than concrete implementations, enabling the bootstrap layer to wire in different backends through configuration alone.

---

## Files & Interfaces

### `compatibility.py` — `ICompatibilityChecker`

Abstract contract for model and deployment validation.

| Method | Signature | Use Case |
|---|---|---|
| `validate_model` | `(model: ModelRecord) → None` | Validate model metadata (capabilities, engine support). Raises on failure. |
| `validate_deployment` | `(model: ModelRecord, request: DeploymentCreateRequest) → None` | Validate a deployment request against model and platform constraints. |
| `inspect_huggingface_repo` | `(hf_repo: str, revision: str \| None) → ValidationReport` | Inspect a HuggingFace repository and return a compatibility report. |

---

### `lifecycle.py` — `ILifecycleManager`

Abstract lifecycle manager for deployment state transitions.

| Method | Signature | Use Case |
|---|---|---|
| `initialize` | `(deployment: DeploymentRecord) → LifecycleRecord` | Create an initial lifecycle record (HOT state) for a new deployment. |
| `touch` | `(record: LifecycleRecord) → LifecycleRecord` | Mark a deployment as recently used — resets idle timer to HOT. |
| `reconcile` | `(record: LifecycleRecord) → LifecycleRecord` | Apply policy transitions (HOT → WARM → COLD) based on idle duration. |

---

### `model_server.py` — `IModelServer`

Abstract serving engine contract. Any runtime backend (vLLM, TGI, Transformers, Fake) must implement this.

| Method | Signature | Use Case |
|---|---|---|
| `deploy` | `(model: ModelRecord, request: DeploymentCreateRequest) → DeploymentRecord` | Deploy a model and return deployment metadata. |
| `unload` | `(deployment_id: str) → None` | Unload a deployment from the serving backend. |
| `health` | `() → dict[str, str \| list[str]]` | Return backend-specific health metadata. |
| `generate` | `(deployment: DeploymentRecord, request: ChatCompletionRequest) → str` | Generate model output for a chat completion request. |

---

### `plugin.py` — `IPlugin` & `PluginManifest`

Abstract plugin contract and manifest schema.

| Class | Description |
|---|---|
| `PluginManifest` | Pydantic model declaring a plugin's `plugin_id`, `family`, `supported_engines`, `capabilities`, and free-form `metadata`. |
| `IPlugin` | Abstract base requiring `manifest` property and `register()` method. |

| Method / Property | Signature | Use Case |
|---|---|---|
| `manifest` | `→ PluginManifest` (property) | Return the plugin's declarative manifest. |
| `register` | `() → PluginManifest` | Register plugin metadata with the platform, returning the manifest. |

---

### `registry.py` — `IRegistry`

Service-level registry contract orchestrating model, deployment, and lifecycle persistence.

| Method | Signature | Use Case |
|---|---|---|
| `register_model` | `(request: ModelRegistrationRequest) → ModelRecord` | Register a model in the registry. |
| `get_model` | `(model_id: str) → ModelRecord` | Load a model by ID. |
| `list_models` | `() → list[ModelRecord]` | List all models. |
| `update_model` | `(model: ModelRecord) → ModelRecord` | Persist a model update. |
| `create_deployment` | `(request: DeploymentCreateRequest) → DeploymentRecord` | Create a deployment record. |
| `get_deployment` | `(deployment_id: str) → DeploymentRecord` | Load a deployment by ID. |
| `list_deployments` | `() → list[DeploymentRecord]` | List all deployments. |
| `update_deployment` | `(deployment: DeploymentRecord) → DeploymentRecord` | Persist a deployment update. |
| `get_lifecycle` | `(deployment_id: str) → LifecycleRecord \| None` | Load lifecycle state for a deployment. |
| `upsert_lifecycle` | `(record: LifecycleRecord) → LifecycleRecord` | Create or update lifecycle state. |

---

### `repositories.py` — Repository Interfaces

Low-level persistence contracts isolated from SQLAlchemy.

| Interface | Methods | Use Case |
|---|---|---|
| `IModelRepository` | `save`, `get`, `list` | CRUD for model records. |
| `IDeploymentRepository` | `save`, `get`, `list` | CRUD for deployment records. |
| `ILifecycleRepository` | `save`, `get`, `list` | CRUD for lifecycle state. |
| `ITelemetryRepository` | `save`, `list`, `snapshot` | CRUD and aggregate metrics for telemetry events. |

---

### `router.py` — `IRouter`

Abstract routing contract for deployment selection.

| Method | Signature | Use Case |
|---|---|---|
| `route` | `(request: RouteRequest, models: list[ModelRecord], deployments: list[DeploymentRecord], lifecycle_records: list[LifecycleRecord]) → RouteDecision` | Select a compatible deployment for the incoming request based on capability, status, and lifecycle health. |

---

### `telemetry.py` — `ITelemetryProvider`

Abstract telemetry sink contract.

| Method | Signature | Use Case |
|---|---|---|
| `emit` | `(event: TelemetryEvent) → None` | Emit a telemetry event to the configured sink. |
| `snapshot` | `() → MetricsSnapshot` | Return current aggregate metrics (total requests, errors, average latency). |
