# `tests/unit/` — Unit Tests

Fast, isolated unit tests targeting individual components. Each test uses in-memory repositories and the `FakeModelServer` to avoid external dependencies, database I/O, or ML library imports.

---

## Test Files

| File | Component Under Test | Key Scenarios |
|---|---|---|
| `test_config_loader.py` | `ConfigLoader` | YAML file loading, environment variable merging (`LLM_PLATFORM__*`), Pydantic model validation, missing file handling. |
| `test_lifecycle.py` | `SimpleLifecycleManager` | `initialize` creates HOT record, `touch` resets to HOT, `reconcile` transitions to WARM/COLD based on idle thresholds. |
| `test_model_management.py` | `ModelManagementService` | Model registration with validation, deploy workflow (validate → deploy → READY → lifecycle init), unload workflow. |
| `test_placement.py` | `resolve_placement`, `discover_placement_availability` | Preferred placement selection, fallback chain, CPU default, unavailable placement error. |
| `test_plugins.py` | `PluginManager` | Plugin registration, duplicate ID detection (`ConflictError`), manifest listing, `NotFoundError` on missing plugin. |
| `test_remote_model_server.py` | `OpenAICompatibleRemoteModelServer` | Deploy with health check, generate via HTTP mock, base URL resolution, remote model name resolution. |
| `test_routing.py` | `CapabilityRouter` | Capability matching, preferred model priority, skip non-READY deployments, skip FAILED lifecycle, `RoutingError` when no match. |
| `test_serving_factory.py` | `build_model_server` | Returns correct backend class for each `implementation` value, raises `ValidationError` for unsupported values. |
