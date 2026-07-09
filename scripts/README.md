# `scripts/` — CLI Scripts & Automation

Command-line scripts for common platform operations: bootstrapping the database, registering/deploying models, running validation, and smoke testing the local hosting stack.

---

## Files & Functions

### `bootstrap.py` — Database & Sample Data Initialization

Local bootstrap entrypoint that runs Alembic migrations and optionally loads sample model data from a catalog YAML.

| Function | Signature | Use Case |
|---|---|---|
| `load_platform_config` | `(config_path: Path = DEFAULT_CONFIG_PATH) → PlatformConfig` | Load and validate the platform configuration YAML. |
| `run_migrations` | `(config_path: Path = DEFAULT_CONFIG_PATH) → None` | Run Alembic migrations to `head` using the database URL from platform config. Creates SQLite parent directories if needed. |
| `resolve_catalog_path` | `(config_path: Path, catalog_path: Path \| None) → Path` | Resolve the model catalog YAML path — checks for a co-located catalog first, then falls back to `configs/models/catalog.yaml`. |
| `load_sample_data` | `(config_path: Path, catalog_path: Path \| None) → None` | Build the platform application, then register and deploy each model from the catalog YAML. Skips if models already exist. |
| `bootstrap` | `(config_path: Path, catalog_path: Path \| None) → None` | **Main entrypoint** — runs migrations then loads sample data. |

**Usage:**
```bash
python scripts/bootstrap.py
```

---

### `register_model.py` — Model Registration CLI

Register a model from a YAML document into the platform registry.

| Function | Signature | Use Case |
|---|---|---|
| `parse_args` | `() → argparse.Namespace` | Parse `--config` and `--model-yaml` arguments. |
| `main` | `() → None` | Load the model YAML, validate and register each model, print the resulting model ID, name, and engine. |

**Usage:**
```bash
python scripts/register_model.py --model-yaml configs/models/qwen3_1_7b.yaml
python scripts/register_model.py --config configs/platform.yaml --model-yaml my_model.yaml
```

---

### `deploy_model.py` — Model Deployment CLI

Deploy a registered model through the platform service layer.

| Function | Signature | Use Case |
|---|---|---|
| `parse_args` | `() → argparse.Namespace` | Parse `--config`, `--model-id`, `--endpoint`, `--engine`, `--placement` arguments. |
| `main` | `() → None` | Build the application, deploy the model, and print the deployment ID and endpoint. |

**Usage:**
```bash
python scripts/deploy_model.py --model-id <UUID> --endpoint http://localhost:9000/models/my-model
python scripts/deploy_model.py --model-id <UUID> --endpoint local://my-model --placement mps
```

---

### `validate_model.py` — HuggingFace Model Validation CLI

Inspect a HuggingFace model repository and emit a JSON compatibility report.

| Function | Signature | Use Case |
|---|---|---|
| `parse_args` | `() → argparse.Namespace` | Parse `--hf-repo`, `--revision`, `--compatibility-config` arguments. |
| `main` | `() → None` | Create an inspector, inspect the repository, and print the validation report as formatted JSON. |

**Usage:**
```bash
python scripts/validate_model.py --hf-repo Qwen/Qwen2.5-7B-Instruct
python scripts/validate_model.py --hf-repo meta-llama/Llama-3-8B --revision main
```

---

### `smoke_test_hosting.py` — End-to-End Hosting Smoke Test

Registers a model, deploys it through the HuggingFace Transformers backend, runs a single chat completion, and unloads the deployment. Designed for developer validation on CPU, CUDA, or Apple Metal MPS.

| Function | Signature | Use Case |
|---|---|---|
| `build_config` | `(database_path: Path, placement: str) → PlatformConfig` | Build a runtime config targeting the local Transformers backend with the specified placement. |
| `run_smoke_test` | `(model_source_id: str, placement: str) → str` | **Full E2E flow:** create SQLite DB → build app → register model → deploy → chat completion → unload → return response. |
| `parse_args` | `() → argparse.Namespace` | Parse `--model-source-id` and `--placement` arguments. |
| `main` | `() → None` | Run the smoke test and print the generated response. |

**Usage:**
```bash
python scripts/smoke_test_hosting.py --model-source-id Qwen/Qwen3-1.7B --placement mps
python scripts/smoke_test_hosting.py --placement cpu
```
