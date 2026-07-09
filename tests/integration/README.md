# `tests/integration/` — Integration Tests

Multi-component integration tests exercising real SQLAlchemy repositories, full application bootstrap, and HTTP gateway endpoints via FastAPI's `TestClient`.

---

## Test Files

| File | Components Under Test | Key Scenarios |
|---|---|---|
| `test_bootstrap.py` | `PlatformApplicationBuilder`, `PlatformApplication` | Full application assembly from config, all services wired correctly, plugin loading, repository creation. |
| `test_gateway.py` | Gateway HTTP routes, `ModelManagementService`, `ChatService` | Model registration via POST, model deployment via POST, chat completion via POST, health endpoint, error handling (404, 400). |
| `test_openai_gateway.py` | `/v1/` OpenAI-compatible routes | Chat completion returns `choices[]` format, `finish_reason: "stop"`, correct `model` field, usage block present. |
| `test_sqlalchemy_repositories.py` | `SQLAlchemyModelRepository`, `SQLAlchemyDeploymentRepository`, `SQLAlchemyLifecycleRepository`, `SQLAlchemyTelemetryRepository` | Save/get/list operations, `NotFoundError` for missing records, telemetry `snapshot()` aggregation, foreign key relationships. |

---

## Database

Integration tests use a SQLite database at `./data/test-platform.db`. The `conftest.py` helper creates the schema automatically via `Base.metadata.create_all`.
