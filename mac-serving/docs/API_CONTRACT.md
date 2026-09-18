# Foundation Mac Serving API Contract

Contract version: `1.0.0`
Service version: `0.1.0`
Validated: `2026-09-18`
Base URL: `http://127.0.0.1:8080`

This contract covers the locally hosted `google/gemma-4-E4B` base model using
the `ggml-org/gemma-4-E4B-GGUF` Q8_0 artifact and llama.cpp build 10964.

## Compatibility and scope

- The supported inference operation is text completion at
  `POST /v1/completions`.
- The model identifier is exactly `gemma-4-E4B`.
- This is a pretrained base model. `POST /v1/chat/completions` is not part of
  this contract; use the separate instruction-tuned model for chat semantics.
- `/v1/*` requests and responses are passed through to llama.cpp. Fields listed
  below are the stable subset validated for this deployment.
- Each server slot has a maximum context of 16,384 tokens. Prompt plus generated
  tokens must fit within that limit.
- JSON uses UTF-8. Unknown optional fields are forwarded to the backend and may
  be rejected there.

## Authentication

The default loopback deployment does not require authentication.

If `MAC_SERVING_API_KEY` is set, every `/v1/*` request must include:

```http
Authorization: Bearer <MAC_SERVING_API_KEY>
```

Administrative health, footprint, and metrics endpoints remain unauthenticated
and should therefore stay on a trusted interface. The configuration refuses a
non-loopback bind unless `MAC_SERVING_API_KEY` is set.

## Text completion

### Request

```http
POST /v1/completions HTTP/1.1
Host: 127.0.0.1:8080
Content-Type: application/json
```

```json
{
  "model": "gemma-4-E4B",
  "prompt": "Foundation AI platforms should be efficient because",
  "max_tokens": 128,
  "temperature": 0,
  "top_p": 0.95,
  "stream": false,
  "stop": ["\n\n"]
}
```

| Field | Type | Required | Contract |
|---|---|---:|---|
| `model` | string | yes | Must be `gemma-4-E4B`. |
| `prompt` | string | yes | Text to continue. |
| `max_tokens` | integer | recommended | Maximum generated tokens; must leave room inside the 16,384-token slot. |
| `temperature` | number | no | Sampling temperature. `0` is useful for deterministic tests. |
| `top_p` | number | no | Nucleus-sampling threshold from `0` to `1`. |
| `top_k` | integer | no | llama.cpp extension limiting candidates per token. |
| `stream` | boolean | no | When `true`, returns Server-Sent Events. Default is non-streaming. |
| `stop` | string or string[] | no | Stop sequence or sequences. |
| `seed` | integer | no | Sampling seed. |

### Successful non-streaming response

Status: `200 OK`
Content-Type: `application/json`

```json
{
  "id": "chatcmpl-Wm8hV4uSPMwDQ3gJbLdNX75HA6dYRAwT",
  "object": "text_completion",
  "created": 1789752993,
  "model": "gemma-4-E4B",
  "system_fingerprint": "b10964-b29c606e2",
  "choices": [
    {
      "text": " they are the foundation of your AI strategy.",
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "completion_tokens": 10,
    "prompt_tokens": 8,
    "total_tokens": 18,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  },
  "timings": {
    "cache_n": 0,
    "prompt_n": 8,
    "prompt_ms": 96.532,
    "prompt_per_token_ms": 12.0665,
    "prompt_per_second": 82.874,
    "predicted_n": 10,
    "predicted_ms": 170.0,
    "predicted_per_token_ms": 17.0,
    "predicted_per_second": 58.82
  }
}
```

Response guarantees:

- `choices` contains at least one result after successful generation.
- `choices[].finish_reason` is normally `stop` or `length`.
- `usage` contains token counts for the complete request.
- `timings` and `system_fingerprint` are llama.cpp extensions. Consumers should
  tolerate additional fields and should not require these extensions when
  swapping to another OpenAI-compatible backend.
- `created`, `id`, and timing values vary per request.

### Streaming response

Set `"stream": true`. The response uses `text/event-stream`. Every event begins
with `data:` and is separated by a blank line:

```text
data: {"choices":[{"text":" the","index":0,"logprobs":null,"finish_reason":null}],"model":"gemma-4-E4B","object":"text_completion","id":"chatcmpl-..."}

data: {"choices":[{"text":" limit","index":0,"logprobs":null,"finish_reason":null}],"model":"gemma-4-E4B","object":"text_completion","id":"chatcmpl-..."}

data: {"choices":[{"text":"","index":0,"logprobs":null,"finish_reason":"length"}],"usage":{"completion_tokens":3,"prompt_tokens":4,"total_tokens":7},"id":"chatcmpl-..."}

data: [DONE]
```

Clients must concatenate `choices[0].text` in arrival order and stop after
`data: [DONE]`. Usage and timing information are normally attached to the final
JSON event.

### Curl examples

Non-streaming:

```bash
curl -sS http://127.0.0.1:8080/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma-4-E4B",
    "prompt": "Foundation AI platforms should be efficient because",
    "max_tokens": 128,
    "temperature": 0
  }'
```

Streaming:

```bash
curl -sN http://127.0.0.1:8080/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma-4-E4B",
    "prompt": "The sky is",
    "max_tokens": 64,
    "stream": true
  }'
```

## Model discovery

### `GET /v1/models`

Status: `200 OK`

The OpenAI-compatible model list is in `data`. llama.cpp also includes a
backend-specific `models` array; consumers should use `data`.

```json
{
  "object": "list",
  "data": [
    {
      "id": "gemma-4-E4B",
      "aliases": ["gemma-4-E4B"],
      "object": "model",
      "owned_by": "llamacpp",
      "meta": {
        "n_vocab": 262144,
        "n_ctx": 16384,
        "n_ctx_train": 131072,
        "n_embd": 2560,
        "n_params": 7518069290,
        "size": 8015415464,
        "ftype": "Q8_0"
      }
    }
  ]
}
```

## Operational endpoints

### `GET /`

```json
{
  "name": "foundation-mac-serving",
  "version": "0.1.0",
  "model": "gemma-4-E4B",
  "api": "/v1/completions"
}
```

### `GET /healthz`

Returns `200` while the control plane is running. `backend` can be `up` or
`down`.

```json
{
  "status": "ok",
  "backend": "up",
  "managed_process": true
}
```

### `GET /readyz`

Returns `200` only when llama.cpp accepts traffic:

```json
{"status":"ready"}
```

Returns `503` while the backend is unavailable:

```json
{"status":"not_ready"}
```

### `GET /footprint`

Returns the live unified-memory estimate. Values are GiB except
`context_per_slot`.

```json
{
  "weights_gib": 7.48,
  "kv_cache_gib": 5.58,
  "compute_workspace_gib": 1.5,
  "control_plane_gib": 0.25,
  "serving_total_gib": 14.81,
  "os_reserve_gib": 12.8,
  "projected_total_gib": 27.61,
  "available_gib": 64.0,
  "headroom_gib": 36.39,
  "fits_safely": true,
  "context_per_slot": 16384
}
```

### `GET /metrics`

Returns Prometheus text format with these stable metric names:

```text
mac_serving_requests_total
mac_serving_failures_total
mac_serving_requests_in_flight
mac_serving_request_duration_seconds_total
mac_serving_uptime_seconds
```

## Errors

| Condition | Status | Body shape |
|---|---:|---|
| Missing or invalid API key | 401 | `{"detail":"invalid API key"}` |
| Missing `prompt` or invalid generation input | 400 | `{"error":{"code":400,"message":"...","type":"invalid_request_error"}}` |
| Backend unavailable through `/v1/*` | 503 | `{"detail":"inference backend unavailable"}` |
| Backend not ready | 503 | `{"status":"not_ready"}` |
| Backend-specific failure | backend status | Passed through unchanged. |

Clients should branch on HTTP status and treat error message text as diagnostic,
not as a stable machine-readable identifier.

## Benchmark baseline

Hardware and runtime:

- MacBook Pro `Mac16,6`
- Apple M4 Max: 12 performance CPU cores and 40 GPU cores
- 64 GiB unified memory; Metal backend
- llama.cpp `0.4.1`, build `10964`, commit `b29c606e2`
- Gemma 4 E4B Q8_0, 7.518B parameters, 8,015,415,464 model bytes
- Flash Attention on; all layers offloaded; Q8_0 K/V cache

### Native engine

Measured with `llama-bench`, after warmup:

| Test | Result | Repetitions |
|---|---:|---:|
| 512-token prompt processing | 1,441.68 tokens/s | 3 |
| 128-token generation | 63.23 tokens/s | 1 |

The prompt-processing standard deviation was 67.29 tokens/s.

### End-to-end HTTP

| Workload | Result |
|---|---:|
| One 64-token completion | 60.07 generated tokens/s |
| One 64-token completion total backend time | 1.132 seconds |
| 8 requests at concurrency 2, 64 tokens each | 107.22 aggregate completion tokens/s |
| Concurrency-2 latency p50 / p95 | 1.161 s / 1.254 s |

Gemma 4 E4B uses large per-layer embedding tables, so natural-language token
access patterns and macOS background memory/I/O activity can produce much lower
sustained results than the native synthetic benchmark. During one background-
loaded repeated-prompt run, throughput fell to 8.56 aggregate tokens/s with a
7.888-second p50. Capacity planning should therefore use a workload-specific
soak test, not only the burst figures above.

Reproduce the API benchmark with:

```bash
.venv/bin/mac-serve benchmark --requests 8 --concurrency 2 --max-tokens 64
```

## Contract evolution

- Additive response fields are non-breaking.
- New optional request fields are non-breaking.
- Removing or renaming fields, changing endpoint semantics, or changing the
  required model identifier requires a major contract-version increment.
- Performance measurements are baselines, not latency or throughput guarantees.
