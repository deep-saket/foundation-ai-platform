# `plugins/` — Model Family Plugins

A plugin system for declaring model family metadata (supported engines, capabilities). Plugins are registered at bootstrap time based on the `plugins.enabled` configuration list. Each plugin provides a declarative `PluginManifest` that the platform uses to understand what model families are available.

---

## Architecture

```
IPlugin (interface)
  └── BasePlugin (base implementation with static manifest)
        ├── QwenPlugin
        ├── LlamaPlugin
        ├── MistralPlugin
        └── DeepSeekPlugin
```

---

## Core Files

### `base.py` — `BasePlugin`

Base plugin implementation that wraps a static `PluginManifest`.

| Method / Property | Signature | Use Case |
|---|---|---|
| `__init__` | `(manifest: PluginManifest)` | Store the manifest provided by the concrete plugin subclass. |
| `manifest` | `→ PluginManifest` (property) | Return the plugin's declarative manifest. |
| `register` | `() → PluginManifest` | Return the manifest (used during plugin registration). |

### `manager.py` — `PluginManager`

Central registry for active plugins. Prevents duplicate registrations.

| Method | Signature | Use Case |
|---|---|---|
| `__init__` | `()` | Initialize an empty plugin dictionary. |
| `register` | `(plugin: IPlugin) → PluginManifest` | Register a plugin instance. Raises `ConflictError` if the `plugin_id` is already registered. |
| `get` | `(plugin_id: str) → IPlugin` | Retrieve a registered plugin by ID. Raises `NotFoundError` if not found. |
| `manifests` | `() → list[PluginManifest]` | Return a list of all registered plugin manifests. |

---

## Plugin Implementations

### `qwen/plugin.py` — `QwenPlugin`

| Field | Value |
|---|---|
| Plugin ID | `qwen` |
| Family | `qwen` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning`, `tool_calling` |

### `llama/plugin.py` — `LlamaPlugin`

| Field | Value |
|---|---|
| Plugin ID | `llama` |
| Family | `llama` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning` |

### `mistral/plugin.py` — `MistralPlugin`

| Field | Value |
|---|---|
| Plugin ID | `mistral` |
| Family | `mistral` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `embedding`, `classification` |

### `deepseek/plugin.py` — `DeepSeekPlugin`

| Field | Value |
|---|---|
| Plugin ID | `deepseek` |
| Family | `deepseek` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning`, `evaluation` |
