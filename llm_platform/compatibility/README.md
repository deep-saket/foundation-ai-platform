# `compatibility/` — Model Compatibility Validation

This module validates that models and deployments conform to platform-supported engines, and inspects HuggingFace model repositories for backend compatibility recommendations.

---

## Files & Classes

### `checker.py` — `DefaultCompatibilityChecker`

Policy-based compatibility checker used by the model management service before registration and deployment.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(supported_engines: set[str], compatibility_config_path: str \| Path \| None)` | Initialize with the set of engines the platform supports and an optional path to the backend compatibility YAML. |
| `validate_model` | `(model: ModelRecord) → None` | Ensures a model declares at least one capability and uses a supported engine. Raises `ValidationError` on failure. |
| `validate_deployment` | `(model: ModelRecord, request: DeploymentCreateRequest) → None` | Ensures the deployment engine matches the model engine and is supported. Raises `ValidationError` on failure. |
| `inspect_huggingface_repo` | `(hf_repo: str, revision: str \| None) → ValidationReport` | Delegates to `HuggingFaceModelInspector` to produce a full compatibility report for a HuggingFace repository. |

---

### `inspector.py` — `HuggingFaceModelInspector`

Inspects HuggingFace model repositories to recommend a serving backend and assess readiness for platform onboarding.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `(compatibility_config_path: str \| Path)` | Load architecture-to-backend compatibility rules from a YAML configuration file. |
| `inspect` | `(hf_repo: str, revision: str \| None) → ValidationReport` | Queries HuggingFace Hub API, downloads model config and tokenizer, inspects architecture, estimates GPU memory from safetensors, checks chat template availability, and returns a structured `ValidationReport`. |
| `_choose_backend` | `(architecture: str \| None) → tuple[str, str]` | Internal — selects a recommended backend (`vllm`, `tgi`, or `huggingface-transformers`) based on config-driven architecture rules. Returns `("manual_review", "unsupported")` for unknown architectures. |
| `_load_config` | `(path: str \| Path) → dict` | Internal — loads the YAML backend compatibility rules file. |

---

## Dependencies

- Requires `huggingface_hub` and `transformers` libraries for the `inspect` method (lazy import).
- Configuration-driven via `configs/validation/backend_compatibility.yaml`.
