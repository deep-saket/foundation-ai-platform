"""Capability-based routing with GPU-aware scheduling.

Decision tree:
1. Find all models matching the requested capability.
2. Among their deployments:
   a. READY + idle (lifecycle HOT/WARM) → serve immediately, prefer models
      with the most capabilities (breadth-first), then random tie-break.
   b. All READY but occupied → check GPU for space:
      - Space available → requires_new_instance=True
      - No space → find idle model to evict → evict_deployment_id set
   c. UNLOADED → cold start (existing behavior)
3. No deployment at all → raise RoutingError
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from llm_platform.interfaces.router import IRouter
from llm_platform.schemas.enums import DeploymentStatus, LifecycleState, ModelStatus
from llm_platform.schemas.registry import DeploymentRecord, LifecycleRecord, ModelRecord
from llm_platform.schemas.routing import RouteDecision, RouteRequest
from llm_platform.utils.errors import RoutingError

if TYPE_CHECKING:
    from llm_platform.services.gpu_tracker import GPUResourceTracker
    from llm_platform.services.concurrency import ConcurrencyTracker

logger = logging.getLogger(__name__)


class CapabilityRouter(IRouter):
    """Select a healthy deployment that satisfies the requested capability with
    GPU-aware scheduling, load balancing, and eviction support."""

    def __init__(
        self, 
        gpu_tracker: "GPUResourceTracker | None" = None,
        concurrency_tracker: "ConcurrencyTracker | None" = None,
    ) -> None:
        self._gpu_tracker = gpu_tracker
        self._concurrency_tracker = concurrency_tracker

    def route(
        self,
        request: RouteRequest,
        models: list[ModelRecord],
        deployments: list[DeploymentRecord],
        lifecycle_records: list[LifecycleRecord],
    ) -> RouteDecision:
        lifecycle_by_deployment = {r.deployment_id: r for r in lifecycle_records}

        # Build a map of model_id -> list[deployment] (multiple containers possible)
        deployments_by_model: dict[str, list[DeploymentRecord]] = {}
        for dep in deployments:
            deployments_by_model.setdefault(dep.model_id, []).append(dep)

        # ── Phase 1: Collect capable models ──────────────────────────
        capable_models: list[ModelRecord] = []
        for model in models:
            if model.status not in {ModelStatus.REGISTERED, ModelStatus.DEPLOYED}:
                continue
            if request.capability not in model.capabilities:
                continue
            capable_models.append(model)

        if not capable_models:
            raise RoutingError(
                f"No model registered with capability: {request.capability}"
            )

        # Sort capable models by capability breadth (more capabilities = more reusable)
        capable_models.sort(key=lambda m: len(m.capabilities), reverse=True)

        # ── Phase 2: Categorize deployments ──────────────────────────
        ready_idle: list[tuple[ModelRecord, DeploymentRecord]] = []
        ready_busy: list[tuple[ModelRecord, DeploymentRecord]] = []
        booting: list[tuple[ModelRecord, DeploymentRecord]] = []
        sitting_on_disk: list[tuple[ModelRecord, DeploymentRecord]] = []

        for model in capable_models:
            model_deployments = deployments_by_model.get(model.id, [])
            if not model_deployments:
                sitting_on_disk.append((model, None))
                continue

            for dep in model_deployments:
                lifecycle = lifecycle_by_deployment.get(dep.deployment_id)
                if lifecycle and lifecycle.state == LifecycleState.FAILED:
                    continue
                # Skip permanently broken deployments
                if dep.status == DeploymentStatus.FAILED:
                    continue

                if dep.status == DeploymentStatus.READY:
                    # Preferred model shortcut
                    if request.preferred_model_id and model.id == request.preferred_model_id:
                        return RouteDecision(
                            model_id=model.id,
                            deployment_id=dep.deployment_id,
                            endpoint=dep.endpoint,
                            capability=request.capability,
                            reason="Matched preferred model and capability with ready deployment",
                            requires_cold_start=False,
                        )

                    if lifecycle and lifecycle.state in {LifecycleState.HOT, LifecycleState.WARM}:
                        is_busy = False
                        if self._concurrency_tracker:
                            is_busy = self._concurrency_tracker.get_active_requests(dep.deployment_id) > 0
                        
                        if is_busy:
                            ready_busy.append((model, dep))
                        else:
                            ready_idle.append((model, dep))
                    else:
                        # HOT lifecycle not yet initialized, treat as idle
                        ready_idle.append((model, dep))
                elif dep.status in {DeploymentStatus.UNLOADED, DeploymentStatus.PENDING}:
                    is_allocated = self._gpu_tracker and dep.deployment_id in self._gpu_tracker.allocations
                    if is_allocated:
                        booting.append((model, dep))
                    else:
                        sitting_on_disk.append((model, dep))

        # ── Phase 3: Route Decision ──────────────────────────────────

        # 3a. Serve from idle READY deployment (load balanced)
        if ready_idle:
            selected_model, selected_dep = random.choice(ready_idle)
            return RouteDecision(
                model_id=selected_model.id,
                deployment_id=selected_dep.deployment_id,
                endpoint=selected_dep.endpoint,
                capability=request.capability,
                reason=f"Load balanced across {len(ready_idle)} idle deployment(s) "
                       f"(model has {len(selected_model.capabilities)} capabilities)",
                requires_cold_start=False,
            )

        # 3b. All running deployments are busy (or none exist). Try to Scale-Out using fresh models!
        if sitting_on_disk:
            # We want to spin up a new model from sitting_on_disk
            scale_out_candidates = []
            for model, dep in sitting_on_disk:
                if self._gpu_tracker:
                    if self._gpu_tracker.can_fit(model.memory_requirement_gb):
                        scale_out_candidates.append((model, dep, None))
                    else:
                        evict_id = self._gpu_tracker.find_evictable(request.metadata.get("_registry"), model.memory_requirement_gb)
                        if evict_id:
                            scale_out_candidates.append((model, dep, evict_id))
                else:
                    scale_out_candidates.append((model, dep, None))

            # If GPU is currently full but nothing is evictable (all models still booting),
            # still queue a cold start — the _global_boot_lock will serialize it safely.
            if not scale_out_candidates:
                scale_out_candidates = [(model, dep, None) for model, dep in sitting_on_disk]

            if scale_out_candidates:
                # Prioritize preferred_model_id if specified
                if request.preferred_model_id:
                    scale_out_candidates.sort(key=lambda c: c[0].id != request.preferred_model_id)
                selected_model, selected_dep, evict_id = scale_out_candidates[0]
                dep_id = selected_dep.deployment_id if selected_dep else None
                endpoint = selected_dep.endpoint if selected_dep else None
                
                reason = "Cold start"
                if ready_busy:
                    reason = f"Scale-out: All {len(ready_busy)} running deployments are busy, spinning up new instance"
                if evict_id:
                    reason += f" (evicting {evict_id} for GPU space)"
                elif self._gpu_tracker:
                    reason += f" (GPU has {self._gpu_tracker.available_vram_gb}GB free, queuing behind boot lock)"

                return RouteDecision(
                    model_id=selected_model.id,
                    deployment_id=dep_id,
                    endpoint=endpoint,
                    capability=request.capability,
                    reason=reason,
                    requires_cold_start=True,
                    evict_deployment_id=evict_id,
                )

        # 3c. Fallback: Queue on active/booting deployments using Power of Two Choices load balancing
        active_deployments = ready_busy + booting
        if active_deployments:
            if len(active_deployments) == 1:
                selected_model, selected_dep = active_deployments[0]
            else:
                c1, c2 = random.sample(active_deployments, 2)
                load1 = self._concurrency_tracker.get_active_requests(c1[1].deployment_id) if self._concurrency_tracker else 0
                load2 = self._concurrency_tracker.get_active_requests(c2[1].deployment_id) if self._concurrency_tracker else 0
                selected_model, selected_dep = c1 if load1 <= load2 else c2

            is_booting = selected_dep.status in {DeploymentStatus.UNLOADED, DeploymentStatus.PENDING}
            
            return RouteDecision(
                model_id=selected_model.id,
                deployment_id=selected_dep.deployment_id,
                endpoint=selected_dep.endpoint,
                capability=request.capability,
                reason=f"Concurrency fallback: Queuing on {'booting' if is_booting else 'busy'} deployment (Power of Two Choices)",
                requires_cold_start=is_booting,
            )

        raise RoutingError(
            f"No eligible deployment found for capability: {request.capability}"
        )
