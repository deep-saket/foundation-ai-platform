# Model artifact

The active runtime model is downloaded from:

- Source model: `google/gemma-4-E4B`
- GGUF conversion: `ggml-org/gemma-4-E4B-GGUF`
- File: `gemma-4-E4B-Q8_0.gguf`
- Size: `8,031,223,872` bytes
- SHA-256: `b6ad9a0a0ce1f9a65d30d8e95f20fd9d2ff93330a5d1e912dc843aa5ad627cef`

The GGUF itself is intentionally excluded from Git. Verify a fresh download with:

```bash
shasum -a 256 gemma-4-E4B-Q8_0.gguf
```
