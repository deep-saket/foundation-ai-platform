"""GPU VRAM resource tracking for capability-based scheduling.

This module provides bookkeeping-based GPU memory tracking. It does NOT
poll nvidia-smi; instead it maintains a ledger of allocated VRAM based on
each model's declared memory_requirement_gb. This is intentional — it avoids
a runtime dependency on pynvml and works reliably across all environments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_platform.interfaces.registry import IRegistry

logger = logging.getLogger(__name__)


class GPUResourceTracker:
    """Track GPU VRAM allocation via bookkeeping."""

    def __init__(self, total_vram_gb: int = 18) -> None:
        self._total_vram_gb = total_vram_gb
        # deployment_id -> allocated GB
        self._allocated: dict[str, int] = {}

    # ── Public Properties ────────────────────────────────────────────

    @property
    def total_vram_gb(self) -> int:
        return self._total_vram_gb

    @property
    def allocated_vram_gb(self) -> int:
        return sum(self._allocated.values())

    @property
    def available_vram_gb(self) -> int:
        return self._total_vram_gb - self.allocated_vram_gb

    @property
    def allocations(self) -> dict[str, int]:
        """Return a copy of the current allocation map."""
        return dict(self._allocated)

    # ── Core Operations ──────────────────────────────────────────────

    def can_fit(self, memory_requirement_gb: int) -> bool:
        """Check if there is enough VRAM headroom for a new model."""
        return self.available_vram_gb >= memory_requirement_gb

    def allocate(self, deployment_id: str, memory_gb: int) -> None:
        """Record a VRAM allocation for a deployment."""
        self._allocated[deployment_id] = memory_gb
        logger.info(
            f"[GPU Tracker] Allocated {memory_gb}GB for deployment {deployment_id}. "
            f"Used: {self.allocated_vram_gb}/{self._total_vram_gb}GB"
        )

    def release(self, deployment_id: str) -> None:
        """Release the VRAM allocation for a deployment."""
        freed = self._allocated.pop(deployment_id, 0)
        if freed:
            logger.info(
                f"[GPU Tracker] Released {freed}GB from deployment {deployment_id}. "
                f"Used: {self.allocated_vram_gb}/{self._total_vram_gb}GB"
            )

    def find_evictable(
        self,
        registry: IRegistry,
        needed_gb: int,
    ) -> str | None:
        """Find an idle deployment to evict to free up needed_gb of VRAM.

        Strategy:
        - Look at all currently allocated deployments
        - Find ones whose lifecycle state is WARM or COLD (i.e. idle)
        - Pick the one with the longest idle time
        - Only return it if evicting it would free enough VRAM

        Returns:
            deployment_id to evict, or None if no suitable candidate exists.
        """
        from llm_platform.schemas.enums import DeploymentStatus, LifecycleState

        best_candidate: str | None = None
        best_idle_seconds: int = -1

        for deployment_id in list(self._allocated.keys()):
            try:
                deployment = registry.get_deployment(deployment_id)
            except Exception:
                continue

            if deployment.status != DeploymentStatus.READY:
                continue
                
            if deployment.metadata.get("is_permanent", False):
                continue

            lifecycle = registry.get_lifecycle(deployment_id)
            if not lifecycle:
                continue

            # Only evict WARM or COLD deployments (idle models)
            if lifecycle.state not in {LifecycleState.WARM, LifecycleState.COLD}:
                continue

            if lifecycle.idle_duration_seconds > best_idle_seconds:
                best_idle_seconds = lifecycle.idle_duration_seconds
                best_candidate = deployment_id

        if best_candidate is not None:
            freed_gb = self._allocated.get(best_candidate, 0)
            if self.available_vram_gb + freed_gb >= needed_gb:
                logger.info(
                    f"[GPU Tracker] Found evictable deployment {best_candidate} "
                    f"(idle {best_idle_seconds}s, freeing {freed_gb}GB)"
                )
                return best_candidate

        return None
