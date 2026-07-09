# `plugins/llama/` — Llama Model Family Plugin

Plugin for Meta's Llama model family. Declares support for vLLM and HuggingFace Transformers serving engines.

---

## Manifest

| Field | Value |
|---|---|
| Plugin ID | `llama` |
| Family | `llama` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning` |

## Class

### `plugin.py` — `LlamaPlugin`

Extends `BasePlugin` with a static `PluginManifest`. No custom logic — all behavior inherited from the base class.

| Method | Inherited From | Use Case |
|---|---|---|
| `manifest` | `BasePlugin` | Returns the Llama manifest. |
| `register` | `BasePlugin` | Registers the manifest with the `PluginManager`. |
