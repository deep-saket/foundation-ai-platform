# `plugins/mistral/` — Mistral Model Family Plugin

Plugin for the Mistral AI model family. Declares support for vLLM and HuggingFace Transformers serving engines.

---

## Manifest

| Field | Value |
|---|---|
| Plugin ID | `mistral` |
| Family | `mistral` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `embedding`, `classification` |

## Class

### `plugin.py` — `MistralPlugin`

Extends `BasePlugin` with a static `PluginManifest`. No custom logic — all behavior inherited from the base class.

| Method | Inherited From | Use Case |
|---|---|---|
| `manifest` | `BasePlugin` | Returns the Mistral manifest. |
| `register` | `BasePlugin` | Registers the manifest with the `PluginManager`. |
