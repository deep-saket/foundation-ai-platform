"""Database table definitions for registry data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column



class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class ModelTable(Base):
    """Persistent model catalog."""

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    family: Mapped[str] = mapped_column(String(128), nullable=False)
    engine: Mapped[str] = mapped_column(String(128), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    vllm_eagle_head: Mapped[str | None] = mapped_column(String(512), nullable=True)
    memory_requirement_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    ownership: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class DeploymentTable(Base):
    """Persistent deployment catalog."""

    __tablename__ = "deployments"

    deployment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), ForeignKey("models.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    engine: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class LifecycleTable(Base):
    """Persistent lifecycle state."""

    __tablename__ = "lifecycle_states"

    deployment_id: Mapped[str] = mapped_column(String(64), ForeignKey("deployments.deployment_id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    last_transition: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)


class TelemetryTable(Base):
    """Persistent request telemetry."""

    __tablename__ = "telemetry"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deployment_id: Mapped[str] = mapped_column(String(64), ForeignKey("deployments.deployment_id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    e2e_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ttft_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tpot_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    itl_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    speculative_decoding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
