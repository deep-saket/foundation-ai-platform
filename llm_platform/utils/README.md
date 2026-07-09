# `utils/` — Shared Utilities

Cross-cutting utility modules used throughout the platform — YAML configuration loading with environment variable overrides, and a custom exception hierarchy.

---

## Files & Classes

### `config_loader.py` — `ConfigLoader`

Loads platform configuration from YAML files and merges environment variable overrides.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(env_prefix: str = "LLM_PLATFORM")` | Configure the environment variable prefix used for overrides. |
| `load` | `(path: str \| Path, model_type: type[T]) → T` | Load YAML from the given path, merge with environment overrides, and validate into the specified Pydantic model. |
| `_read_yaml` | `(path: str \| Path) → dict` | Internal — reads and parses a YAML file. Returns an empty dict if the file doesn't exist. |
| `_read_environment` | `() → dict` | Internal — scans environment variables with the configured prefix (e.g., `LLM_PLATFORM__SERVING__IMPLEMENTATION=fake`) and builds a nested dict. Uses `__` (double underscore) as the nesting separator. |
| `_merge_dicts` | `(base: dict, override: dict) → dict` | Internal — deep-merges the override dict into the base dict. Environment values take precedence over YAML values. |

#### Environment Override Examples

```bash
# Override the serving implementation
LLM_PLATFORM__SERVING__IMPLEMENTATION=fake

# Override the database engine
LLM_PLATFORM__DATABASE__ENGINE=memory

# Override the gateway port
LLM_PLATFORM__GATEWAY__PORT=9000
```

---

### `errors.py` — Platform Exception Hierarchy

Custom exception classes for structured error handling across the platform.

| Exception | Parent | HTTP Status | Use Case |
|---|---|---|---|
| `PlatformError` | `Exception` | 500 | Base exception for all platform-specific errors. |
| `NotFoundError` | `PlatformError` | 404 | Raised when a requested resource (model, deployment, plugin) does not exist. |
| `ConflictError` | `PlatformError` | 409 | Raised when a duplicate or conflicting state is detected (e.g., duplicate plugin ID). |
| `ValidationError` | `PlatformError` | 400 | Raised when validation fails outside of Pydantic models (e.g., unsupported engine, missing metadata). |
| `RoutingError` | `PlatformError` | 400 | Raised when the router cannot find an eligible deployment for the requested capability. |
