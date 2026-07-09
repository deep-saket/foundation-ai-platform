# `registry/` — Registry Service

The service-level boundary for all model, deployment, and lifecycle record persistence. Acts as a thin coordination layer between the repository interfaces and the rest of the platform, ensuring that services never interact with raw repositories directly.

---

## Files & Classes

### `service.py` — `RegistryService`

Implements `IRegistry`. Delegates all persistence operations to the injected repository implementations.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(model_repository: IModelRepository, deployment_repository: IDeploymentRepository, lifecycle_repository: ILifecycleRepository)` | Inject the three repository dependencies used for persistence. |
| `register_model` | `(request: ModelRegistrationRequest) → ModelRecord` | Create a `ModelRecord` from the request and save it to the model repository. |
| `get_model` | `(model_id: str) → ModelRecord` | Load a model by ID from the model repository. Raises `NotFoundError` if absent. |
| `list_models` | `() → list[ModelRecord]` | List all registered models. |
| `update_model` | `(model: ModelRecord) → ModelRecord` | Persist changes to an existing model record (e.g., status transitions). |
| `create_deployment` | `(request: DeploymentCreateRequest) → DeploymentRecord` | Create a new `DeploymentRecord` from the request and save it to the deployment repository. |
| `get_deployment` | `(deployment_id: str) → DeploymentRecord` | Load a deployment by ID. Raises `NotFoundError` if absent. |
| `list_deployments` | `() → list[DeploymentRecord]` | List all deployments. |
| `update_deployment` | `(deployment: DeploymentRecord) → DeploymentRecord` | Persist changes to an existing deployment record (e.g., status to READY or UNLOADED). |
| `get_lifecycle` | `(deployment_id: str) → LifecycleRecord \| None` | Load lifecycle state for a deployment. Returns `None` if no record exists. |
| `upsert_lifecycle` | `(record: LifecycleRecord) → LifecycleRecord` | Create or update a deployment's lifecycle state record. |
