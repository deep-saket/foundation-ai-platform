# Foundation Mac Serving

A small production-shaped serving stack for this Mac. The inference engine is
the native C++ `llama-server` from llama.cpp, compiled with Metal. A thin Python
control plane owns process lifecycle, readiness, footprint reporting, metrics,
and the OpenAI-compatible proxy.

## Profile selected for this machine

The checked-in defaults were generated for the detected host:

| Resource | Detected / configured |
|---|---:|
| Mac | MacBook Pro `Mac16,6` |
| SoC | Apple M4 Max |
| CPU / GPU | 16 CPU cores (12 performance), 40 GPU cores |
| Unified memory | 64 GiB |
| Default model | Gemma 4 E4B base, GGUF `Q8_0` |
| Aggregate context | 65,536 tokens |
| Continuous-batching slots | 4 (16,384 tokens/slot) |
| KV cache | `q8_0` K and V |
| GPU offload | all layers (`all`) |

The selected model is the exact `google/gemma-4-E4B` base model requested,
distributed in GGUF form by the llama.cpp maintainers. E4B means 4.5B effective
parameters; per-layer embeddings bring the stored total to roughly 8B. The Q8_0
file is about 7.5 GiB and preserves substantially more quality than aggressive
4-bit quantization for this architecture. The planner budgets its KV cache,
compute/control overhead, and 12.8 GiB for macOS. The actual GGUF file size
replaces the pre-download estimate automatically.

This profile prioritizes low latency and efficient multi-client serving. It uses
only a fraction of the Mac's unified memory and leaves ample room for development
tools and other applications.

## Architecture

```text
OpenAI client :8080
        |
        v
FastAPI control plane (~250 MiB budget)
  health | auth | metrics | footprint | streaming proxy
        |
        v
llama-server :8081 (loopback only)
  Metal + full GPU offload + continuous batching + quantized KV
        |
        v
GGUF model in unified memory
```

The backend is deliberately isolated on loopback. The public control-plane bind
also defaults to loopback; setting it to a LAN address is rejected unless
`MAC_SERVING_API_KEY` is set.

## Install

Prerequisites are Xcode Command Line Tools, CMake, Git, and Python 3.11+.
If CMake is missing, install it with `brew install cmake`, then run:

```bash
cd mac-serving
make bootstrap
```

`bootstrap.sh` creates `.venv`, installs the Python control plane, shallow-clones
llama.cpp, and builds only `llama-server` in Release mode with Metal and native
CPU tuning. Metal is enabled by default by llama.cpp on macOS; the explicit CMake
flag documents and protects that choice.

Download the configured model:

```bash
./scripts/download_model.sh ggml-org/gemma-4-E4B-GGUF gemma-4-E4B-Q8_0.gguf
```

The file name must match `[model].path` in `config/mac-serving.toml`. The existing
`data/model-cache` contains Transformers safetensors, not GGUF, so it is not used
by this serving path.

## Operate

```bash
# Inspect hardware and estimated memory use; this works before model install.
.venv/bin/mac-serve plan

# Verify Metal host, native binary, model file, bind safety, and memory headroom.
.venv/bin/mac-serve doctor

# Start both the native backend and the API control plane.
.venv/bin/mac-serve serve
```

Then send an OpenAI-compatible request:

```bash
curl http://127.0.0.1:8080/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma-4-E4B",
    "prompt": "Why is unified memory useful?",
    "max_tokens": 128,
    "stream": true
  }'
```

Operational endpoints:

- `GET /healthz` — control plane plus backend state
- `GET /readyz` — returns 503 until inference is ready
- `GET /footprint` — live memory estimate based on the actual model file
- `GET /metrics` — dependency-free Prometheus text metrics
- `/v1/*` — streamed through to llama.cpp without changing the API payload

The complete input/output specification, error shapes, streaming framing, and
benchmark baseline are in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

This exact repository is a pretrained base model, so the primary endpoint is
`/v1/completions`. For instruction-following chat semantics, use Google's
separate `google/gemma-4-E4B-it` model instead.

To connect the control plane to an already managed `llama-server`, set
`engine.manage_process = false`. To expose the API beyond the Mac, set a strong
key before changing `server.host`:

```bash
export MAC_SERVING_API_KEY="$(openssl rand -hex 32)"
```

Clients must then send `Authorization: Bearer $MAC_SERVING_API_KEY`.

## Tune and benchmark

Start with the checked-in balanced profile, then measure your workload:

```bash
.venv/bin/mac-serve benchmark --requests 8 --concurrency 2 --max-tokens 128
```

- Interactive use: set `parallel = 1` or `2`; each slot receives more context
  and time-to-first-token contention is lower.
- Multiple local clients: keep `parallel = 4`; continuous batching improves
  aggregate throughput.
- Longer per-request context: increase `context_size`, remembering that it is
  the aggregate context shared by all slots and KV memory grows linearly.
- Highest output quality within the same model family: use Q5/Q6 weights and let
  `mac-serve plan` recalculate from the real file size before serving.
- If memory pressure appears: reduce context first, then parallelism, then model
  size. Do not enable `mlock` until the profile is stable.

Performance numbers are intentionally not guessed. Run the benchmark after the
specific model is installed; prompt processing, generation speed, and first-token
latency vary substantially by architecture, quantization, and context length.

### Measured on this Mac

With llama.cpp build 10964, the downloaded Q8_0 model, and the checked-in profile:

| Measurement | Result |
|---|---:|
| Native 512-token prompt processing | 1,441.7 tokens/second |
| Native 128-token generation | 63.23 tokens/second |
| Single HTTP generation | 60.07 tokens/second |
| 8 HTTP requests, concurrency 2 | 107.2 completion tokens/second aggregate |
| Concurrency-2 latency p50 / p95 | 1.161 s / 1.254 s |

The concurrent benchmark used 64 output tokens per request. Gemma 4's large
per-layer embeddings make sustained performance sensitive to token patterns and
background memory/I/O load; see the contract's benchmark section for the
observed range and methodology. These are local measurements, not guarantees.

## Development

```bash
.venv/bin/python -m pytest
```

The configuration parser, footprint math, and native command construction are
unit-tested without requiring a model download. Runtime logs go to
`run/llama-server.log`; model files, logs, virtual environments, and vendored
build output are excluded from Git.
