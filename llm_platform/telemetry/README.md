# `telemetry/` — Telemetry Providers

Implements the `ITelemetryProvider` interface with multiple backend strategies for collecting request telemetry (latency, token counts, errors).

---

## Files & Classes

### `providers.py` — Provider Implementations

| Class | Interface | Use Case |
|---|---|---|
| `NoOpTelemetryProvider` | `ITelemetryProvider` | Null object pattern — silently discards all events and returns empty metrics. Used when telemetry is disabled. |
| `MemoryTelemetryProvider` | `ITelemetryProvider` | In-memory telemetry sink backed by an `ITelemetryRepository`. Used for unit tests and local development. Identical in behavior to `RepositoryTelemetryProvider`. |
| `RepositoryTelemetryProvider` | `ITelemetryProvider` | Repository-backed telemetry provider. Persists events via the injected `ITelemetryRepository` (SQLAlchemy or in-memory). Used for production with database persistence. |

### Method Reference

#### `NoOpTelemetryProvider`

| Method | Signature | Use Case |
|---|---|---|
| `emit` | `(event: TelemetryEvent) → None` | Silently discards the event. |
| `snapshot` | `() → MetricsSnapshot` | Returns an empty `MetricsSnapshot` (all zeros). |

#### `MemoryTelemetryProvider` / `RepositoryTelemetryProvider`

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(repository: ITelemetryRepository)` | Inject the repository used for persistence. |
| `emit` | `(event: TelemetryEvent) → None` | Persists the telemetry event to the repository. |
| `snapshot` | `() → MetricsSnapshot` | Returns aggregate metrics (total requests, total errors, average latency) from the repository. |

---

## Provider Selection

The bootstrap layer selects the provider based on `config.telemetry.provider`:

| Config Value | Provider | Repository |
|---|---|---|
| `"memory"` | `MemoryTelemetryProvider` | In-memory telemetry repository |
| `"database"` | `RepositoryTelemetryProvider` | SQLAlchemy telemetry repository |
| Any other value | `NoOpTelemetryProvider` | None |
