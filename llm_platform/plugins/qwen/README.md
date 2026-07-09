# `plugins/qwen/` — Qwen Model Family Plugin

Plugin for the Qwen model family (Alibaba Cloud). Declares support for vLLM and HuggingFace Transformers serving engines.

---

## Manifest

| Field | Value |
|---|---|
| Plugin ID | `qwen` |
| Family | `qwen` |
| Supported Engines | `vllm`, `huggingface-transformers` |
| Capabilities | `chat`, `reasoning`, `tool_calling` |

## Class

### `plugin.py` — `QwenPlugin`

Extends `BasePlugin` with a static `PluginManifest`. No custom logic — all behavior inherited from the base class.

| Method | Inherited From | Use Case |
|---|---|---|
| `manifest` | `BasePlugin` | Returns the Qwen manifest. |
| `register` | `BasePlugin` | Registers the manifest with the `PluginManager`. |
