# `database/` — Persistence Layer

Provides SQLAlchemy ORM table definitions, in-memory and SQL-backed repository implementations, and session management. The database layer is fully isolated behind repository interfaces so the rest of the platform never imports SQLAlchemy directly.

---

## Files & Classes

### `models.py` — ORM Table Definitions

SQLAlchemy declarative models mapping to the relational schema.

| Class | Table | Description |
|---|---|---|
| `Base` | — | SQLAlchemy declarative base class. |
| `ModelTable` | `models` | Persistent model catalog. Columns: `id`, `name`, `version`, `family`, `engine`, `capabilities` (JSON), `memory_requirement_gb`, `ownership`, `status`, `created_at`, `metadata_json` (JSON). |
| `DeploymentTable` | `deployments` | Persistent deployment catalog. Columns: `deployment_id` (PK), `model_id` (FK → models), `endpoint`, `engine`, `status`, `last_used`, `created_at`, `metadata_json` (JSON). |
| `LifecycleTable` | `lifecycle_states` | Persistent lifecycle state per deployment. Columns: `deployment_id` (FK → deployments, PK), `state`, `last_transition`, `idle_duration_seconds`. |
| `TelemetryTable` | `telemetry` | Persistent request telemetry. Columns: `request_id` (PK), `deployment_id` (FK → deployments), `model_name`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `cache_hit`, `error`, `timestamp`, `metadata_json` (JSON). |

---

### `session.py` — `DatabaseSessionManager`

Creates SQLAlchemy engines and transactional sessions from platform configuration.

| Method / Property | Signature | Use Case |
|---|---|---|
| `__init__` | `(config: DatabaseConfig)` | Creates the SQLAlchemy engine and session factory. Auto-creates SQLite parent directories. |
| `engine` | `→ Engine` (property) | Exposes the underlying SQLAlchemy `Engine` for schema creation (`Base.metadata.create_all`). |
| `url` | `→ str` (property) | Returns the computed SQLAlchemy connection URL. |
| `session_scope` | `() → Iterator[Session]` (context manager) | Yields a transactional session and ensures it is closed on exit. |
| `_ensure_sqlite_directory` | `() → None` | Internal — creates the parent directory for SQLite database files. |

---

### `repositories.py` — Repository Implementations

Concrete repository classes implementing the persistence interfaces from `interfaces/repositories.py`.

#### Helper Functions

| Function | Signature | Use Case |
|---|---|---|
| `_model_from_row` | `(row: ModelTable) → ModelRecord` | Converts an ORM row to a Pydantic `ModelRecord`. |
| `_deployment_from_row` | `(row: DeploymentTable) → DeploymentRecord` | Converts an ORM row to a Pydantic `DeploymentRecord`. |
| `_lifecycle_from_row` | `(row: LifecycleTable) → LifecycleRecord` | Converts an ORM row to a Pydantic `LifecycleRecord`. |
| `_telemetry_from_row` | `(row: TelemetryTable) → TelemetryEvent` | Converts an ORM row to a Pydantic `TelemetryEvent`. |

#### In-Memory Repositories (for unit testing)

| Class | Interface | Methods |
|---|---|---|
| `InMemoryModelRepository` | `IModelRepository` | `save(model) → ModelRecord`, `get(model_id) → ModelRecord`, `list() → list[ModelRecord]` |
| `InMemoryDeploymentRepository` | `IDeploymentRepository` | `save(deployment) → DeploymentRecord`, `get(deployment_id) → DeploymentRecord`, `list() → list[DeploymentRecord]` |
| `InMemoryLifecycleRepository` | `ILifecycleRepository` | `save(record) → LifecycleRecord`, `get(deployment_id) → LifecycleRecord \| None`, `list() → list[LifecycleRecord]` |
| `InMemoryTelemetryRepository` | `ITelemetryRepository` | `save(event) → TelemetryEvent`, `list() → list[TelemetryEvent]`, `snapshot() → MetricsSnapshot` |

#### SQLAlchemy Repositories (production persistence)

| Class | Interface | Methods |
|---|---|---|
| `SQLAlchemyModelRepository` | `IModelRepository` | `save(model) → ModelRecord`, `get(model_id) → ModelRecord`, `list() → list[ModelRecord]` |
| `SQLAlchemyDeploymentRepository` | `IDeploymentRepository` | `save(deployment) → DeploymentRecord`, `get(deployment_id) → DeploymentRecord`, `list() → list[DeploymentRecord]` |
| `SQLAlchemyLifecycleRepository` | `ILifecycleRepository` | `save(record) → LifecycleRecord`, `get(deployment_id) → LifecycleRecord \| None`, `list() → list[LifecycleRecord]` |
| `SQLAlchemyTelemetryRepository` | `ITelemetryRepository` | `save(event) → TelemetryEvent`, `list() → list[TelemetryEvent]`, `snapshot() → MetricsSnapshot` (uses SQL aggregate functions) |

#### SQLite Aliases

| Class | Parent | Description |
|---|---|---|
| `SQLiteModelRepository` | `SQLAlchemyModelRepository` | SQLite-specific alias (no extra logic). |
| `SQLiteDeploymentRepository` | `SQLAlchemyDeploymentRepository` | SQLite-specific alias. |
| `SQLiteLifecycleRepository` | `SQLAlchemyLifecycleRepository` | SQLite-specific alias. |
| `SQLiteTelemetryRepository` | `SQLAlchemyTelemetryRepository` | SQLite-specific alias. |
