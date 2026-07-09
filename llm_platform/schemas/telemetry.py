"""Telemetry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    request_id: str
    deployment_id: str
    model_name: str
    latency_ms: float
    # ── Inference Metrics ────────────────────────────────────────────
    e2e_latency_ms: float = 0.0           # End-to-End Latency (full request lifecycle)
    ttft_ms: float = 0.0                  # Time To First Token
    tpot_ms: float = 0.0                  # Time Per Output Token
    itl_ms: float = 0.0                   # Inter-Token Latency (average)
    # ── Token Counts ─────────────────────────────────────────────────
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # ── Flags ────────────────────────────────────────────────────────
    cache_hit: bool = False
    speculative_decoding: bool = False     # Was EAGLE used for this request?
    error: str | None = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricsSnapshot(BaseModel):
    total_requests: int = 0
    total_errors: int = 0
    average_latency_ms: float = 0.0
    # ── Aggregated Inference Metrics ─────────────────────────────────
    average_e2e_latency_ms: float = 0.0
    average_ttft_ms: float = 0.0
    average_tpot_ms: float = 0.0
    average_itl_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    requests_with_speculative_decoding: int = 0
