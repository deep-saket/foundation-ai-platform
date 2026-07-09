# `plugins/deepseek/` — DeepSeek Model Family Plugin

Plugin for the DeepSeek model family. Declares support for vLLM and HuggingFace Transformers serving engines.

---

## Manifest

| Field | Value |
|---|---|
| Plugin ID | `deepseek` |
| Family | `deepseek` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning`, `evaluation` |

## Class

### `plugin.py` — `DeepSeekPlugin`

Extends `BasePlugin` with a static `PluginManifest`. No custom logic — all behavior inherited from the base class.

| Method | Inherited From | Use Case |
|---|---|---|
| `manifest` | `BasePlugin` | Returns the DeepSeek manifest. |
| `register` | `BasePlugin` | Registers the manifest with the `PluginManager`. |
