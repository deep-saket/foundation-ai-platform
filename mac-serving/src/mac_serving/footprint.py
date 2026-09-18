"""Conservative unified-memory estimator for GGUF inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .config import AppConfig
from .hardware import HardwareProfile

GIB = 1024**3


@dataclass(frozen=True, slots=True)
class FootprintEstimate:
    weights_gib: float
    kv_cache_gib: float
    compute_workspace_gib: float
    control_plane_gib: float
    serving_total_gib: float
    os_reserve_gib: float
    projected_total_gib: float
    available_gib: float
    headroom_gib: float
    fits_safely: bool
    context_per_slot: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def estimate_footprint(config: AppConfig, hardware: HardwareProfile) -> FootprintEstimate:
    spec = config.footprint
    engine = config.engine

    if config.model.path.is_file():
        weights = config.model.path.stat().st_size / GIB
    else:
        weights = spec.model_billions * 1e9 * spec.quant_bits / 8 / GIB

    head_dim = spec.head_dim or (spec.hidden_size / spec.attention_heads)
    kv_bytes_per_token = (
        2 * spec.layers * spec.kv_heads * head_dim * spec.cache_bytes
    )
    kv_cache = kv_bytes_per_token * engine.context_size / GIB
    workspace = max(1.5, weights * 0.10)
    control_plane = 0.25
    serving_total = weights + kv_cache + workspace + control_plane
    available = hardware.memory_gib
    os_reserve = max(8.0, available * 0.20)
    projected = serving_total + os_reserve
    headroom = available - projected

    return FootprintEstimate(
        weights_gib=round(weights, 2),
        kv_cache_gib=round(kv_cache, 2),
        compute_workspace_gib=round(workspace, 2),
        control_plane_gib=control_plane,
        serving_total_gib=round(serving_total, 2),
        os_reserve_gib=round(os_reserve, 2),
        projected_total_gib=round(projected, 2),
        available_gib=round(available, 2),
        headroom_gib=round(headroom, 2),
        fits_safely=headroom >= 0,
        context_per_slot=engine.context_size // engine.parallel,
    )


def model_path_status(path: Path) -> str:
    if path.is_file():
        return f"present ({path.stat().st_size / GIB:.2f} GiB)"
    return "missing"
