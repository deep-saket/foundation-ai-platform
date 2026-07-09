"""Registry and deployment schemas.

These models represent the control-plane records exchanged between the gateway,
services, registry, and serving backends. They are intentionally transport-
agnostic so they can be reused by HTTP handlers, scripts, and background jobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from llm_platform.schemas.enums import Capability, DeploymentStatus, LifecycleState, ModelStatus


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class ModelRecord(BaseModel):
    """Persisted model metadata used by routing and deployment."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    family: str
    engine: str
    capabilities: list[Capability | str] = Field(default_factory=list)
    vllm_eagle_head: str | None = None  # HuggingFace repo ID for EAGLE speculative decoding head
    memory_requirement_gb: int
    ownership: str
    status: ModelStatus = ModelStatus.REGISTERED
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentRecord(BaseModel):
    """Persisted deployment metadata used by routing and serving."""

    deployment_id: str = Field(default_factory=lambda: str(uuid4()))
    model_id: str
    endpoint: str
    engine: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    last_used: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifecycleRecord(BaseModel):
    """Persisted lifecycle state for a deployment."""

    deployment_id: str
    state: LifecycleState = LifecycleState.COLD
    last_transition: datetime = Field(default_factory=utcnow)
    idle_duration_seconds: int = 0


class ModelRegistrationRequest(BaseModel):
    """Request payload for model registration."""

    name: str
    version: str
    family: str
    engine: str
    capabilities: list[Capability | str]
    vllm_eagle_head: str | None = None
    memory_requirement_gb: int
    ownership: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentCreateRequest(BaseModel):
    """Request payload for deployment creation.

    Attributes:
        model_id: Platform model identifier to deploy.
        endpoint: Logical endpoint or location exposed by the deployment.
        engine: Optional serving engine override. When omitted, the model's
            registered engine is used.
        placement: Preferred placement such as `cpu`, `mps`, or `cuda`.
        fallback_placements: Ordered fallback placements to consider if the
            preferred placement is unavailable.
        metadata: Free-form runtime metadata such as source model identifiers
            and backend-specific options.
    """

    model_id: str
    endpoint: str
    engine: str | None = None
    placement: str | None = None
    fallback_placements: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
