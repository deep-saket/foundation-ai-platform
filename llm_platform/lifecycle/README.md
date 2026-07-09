# `lifecycle/` — Deployment Lifecycle Management

Manages the state machine governing deployment lifecycle transitions. Deployments progress through thermal states based on idle duration, enabling future resource optimization (e.g., unloading cold deployments).

---

## State Machine

```
HOT  ──(idle ≥ 300s)──▶  WARM  ──(idle ≥ 900s)──▶  COLD
 ▲                                                    │
 └────────────────(request received)──────────────────┘
```

| State | Meaning |
|---|---|
| `HOT` | Deployment is actively serving requests (idle = 0). |
| `WARM` | Deployment has been idle for ≥ 300 seconds (default). |
| `COLD` | Deployment has been idle for ≥ 900 seconds (default). Candidate for unloading. |
| `FAILED` | Deployment is in a failed state and will be skipped by the router. |

---

## Files & Classes

### `manager.py` — `SimpleLifecycleManager`

Implements `ILifecycleManager`. A state-machine skeleton driven by configurable idle timeout thresholds.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(warm_after_seconds: int = 300, cold_after_seconds: int = 900)` | Configure the idle thresholds that trigger state transitions. |
| `initialize` | `(deployment: DeploymentRecord) → LifecycleRecord` | Create an initial lifecycle record in `HOT` state with `idle_duration_seconds = 0`. Called when a deployment is first created. |
| `touch` | `(record: LifecycleRecord) → LifecycleRecord` | Reset a deployment to `HOT` state with zero idle duration. Called on every successful request to mark the deployment as recently used. |
| `reconcile` | `(record: LifecycleRecord) → LifecycleRecord` | Evaluate the current idle duration against thresholds and transition to `WARM` or `COLD` if needed. Returns the record unchanged if no transition is required. Used by background reconciliation loops. |
