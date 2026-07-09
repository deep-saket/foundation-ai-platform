# `tests/` — Test Suite

Organized test suite covering unit, integration, and end-to-end testing of the platform. Uses `pytest` as the test runner with FastAPI's `TestClient` for HTTP-level assertions.

---

## Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Fast, isolated unit tests
├── integration/         # Multi-component integration tests
└── e2e/                 # End-to-end smoke tests
```

---

## Shared Fixtures

### `conftest.py`

| Function | Signature | Use Case |
|---|---|---|
| `build_test_client` | `() → TestClient` | Creates a fully wired FastAPI `TestClient` backed by a SQLite test database (`./data/test-platform.db`). Runs `Base.metadata.create_all` to ensure tables exist. |

---

## Unit Tests (`unit/`)

Fast, isolated tests targeting individual components with in-memory or fake dependencies.

| File | What It Tests |
|---|---|
| `test_config_loader.py` | `ConfigLoader` — YAML loading, environment variable merges, Pydantic validation. |
| `test_lifecycle.py` | `SimpleLifecycleManager` — state transitions (HOT → WARM → COLD), touch resets, reconcile logic. |
| `test_model_management.py` | `ModelManagementService` — registration validation, deploy workflow, unload workflow. |
| `test_placement.py` | `resolve_placement` and `discover_placement_availability` — placement fallback logic. |
| `test_plugins.py` | `PluginManager` — registration, duplicate detection, manifest listing. |
| `test_remote_model_server.py` | `OpenAICompatibleRemoteModelServer` — deploy, generate, health checks against mocked HTTP. |
| `test_routing.py` | `CapabilityRouter` — capability matching, preferred model priority, lifecycle state filtering. |
| `test_serving_factory.py` | `build_model_server` — factory function selects correct backend for each implementation value. |

---

## Integration Tests (`integration/`)

Tests that exercise multiple real components together with a real (SQLite) database.

| File | What It Tests |
|---|---|
| `test_bootstrap.py` | `PlatformApplicationBuilder` — full application assembly from config, service wiring, plugin loading. |
| `test_gateway.py` | Gateway HTTP endpoints — model registration, deployment, chat completion, health via `TestClient`. |
| `test_openai_gateway.py` | OpenAI-compatible `/v1/` endpoints — chat completion response format, choices structure. |
| `test_sqlalchemy_repositories.py` | SQLAlchemy repository implementations — CRUD operations against a real SQLite database. |

---

## End-to-End Tests (`e2e/`)

Full stack smoke tests (may require ML dependencies or running containers).

| File | What It Tests |
|---|---|
| `test_placeholder.py` | Placeholder test to validate the E2E test infrastructure is working. |
