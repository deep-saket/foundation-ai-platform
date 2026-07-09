"""Lifecycle manager implementation."""

from __future__ import annotations

from datetime import datetime, timezone

from llm_platform.interfaces.lifecycle import ILifecycleManager
from llm_platform.schemas.enums import LifecycleState
from llm_platform.schemas.registry import DeploymentRecord, LifecycleRecord


class SimpleLifecycleManager(ILifecycleManager):
    """State-machine skeleton driven by idle timeout thresholds."""

    def __init__(self, warm_after_seconds: int = 300, cold_after_seconds: int = 600) -> None:
        self._warm_after_seconds = warm_after_seconds
        self._cold_after_seconds = cold_after_seconds

    def initialize(self, deployment: DeploymentRecord) -> LifecycleRecord:
        return LifecycleRecord(deployment_id=deployment.deployment_id, state=LifecycleState.HOT, idle_duration_seconds=0)

    def touch(self, record: LifecycleRecord) -> LifecycleRecord:
        return record.model_copy(
            update={
                "state": LifecycleState.HOT,
                "idle_duration_seconds": 0,
                "last_transition": datetime.now(timezone.utc),
            }
        )

    def reconcile(self, record: LifecycleRecord) -> LifecycleRecord:
        idle_seconds = record.idle_duration_seconds
        next_state = record.state
        if idle_seconds >= self._cold_after_seconds:
            next_state = LifecycleState.COLD
        elif idle_seconds >= self._warm_after_seconds:
            next_state = LifecycleState.WARM
        elif idle_seconds == 0:
            next_state = LifecycleState.HOT

        if next_state == record.state:
            return record

        return record.model_copy(update={"state": next_state, "last_transition": datetime.now(timezone.utc)})
