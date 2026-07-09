# `routing/` — Capability-Based Request Routing

Selects the best eligible deployment for an incoming chat completion request by matching requested capabilities against registered models and their active deployments.

---

## Routing Logic

1. **Filter** models by status (`REGISTERED` or `DEPLOYED`) and matching capability.
2. **Prefer** the model matching `preferred_model_id` (if specified in the request).
3. **Check** each model's deployment is in `READY` status.
4. **Skip** deployments whose lifecycle state is `FAILED`.
5. **Return** the first match as a `RouteDecision` containing `model_id`, `deployment_id`, `endpoint`, and `capability`.
6. **Raise** `RoutingError` if no eligible deployment is found.

---

## Files & Classes

### `router.py` — `CapabilityRouter`

Implements `IRouter`. Selects the first healthy deployment that satisfies the requested capability.

| Method | Signature | Use Case |
|---|---|---|
| `route` | `(request: RouteRequest, models: list[ModelRecord], deployments: list[DeploymentRecord], lifecycle_records: list[LifecycleRecord]) → RouteDecision` | Core routing method. Iterates through models in priority order, matches capabilities, validates deployment status and lifecycle health, and returns the first eligible route. |

#### `RouteRequest` Fields

| Field | Type | Description |
|---|---|---|
| `capability` | `Capability \| str` | Required capability (e.g., `"chat"`, `"reasoning"`). |
| `labels` | `dict[str, str]` | Optional label selectors (reserved for future use). |
| `preferred_model_id` | `str \| None` | Optional preferred model to prioritize. |
| `metadata` | `dict[str, Any]` | Free-form metadata passed through to routing decisions. |

#### `RouteDecision` Fields

| Field | Type | Description |
|---|---|---|
| `model_id` | `str` | Selected model identifier. |
| `deployment_id` | `str` | Selected deployment identifier. |
| `endpoint` | `str` | Deployment endpoint URL or address. |
| `capability` | `Capability \| str` | Matched capability. |
| `reason` | `str` | Human-readable explanation of the routing decision. |
