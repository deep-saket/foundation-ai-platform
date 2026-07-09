"""Repository implementations for in-memory and SQLAlchemy-backed persistence."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from llm_platform.database.models import DeploymentTable, LifecycleTable, ModelTable, TelemetryTable
from llm_platform.interfaces.repositories import (
    IDeploymentRepository,
    ILifecycleRepository,
    IModelRepository,
    ITelemetryRepository,
)
from llm_platform.schemas.registry import DeploymentRecord, LifecycleRecord, ModelRecord
from llm_platform.schemas.telemetry import MetricsSnapshot, TelemetryEvent
from llm_platform.utils.errors import NotFoundError

SessionFactory = Callable[[], AbstractContextManager[Session]]


def _model_from_row(row: ModelTable) -> ModelRecord:
    return ModelRecord(
        id=row.id,
        name=row.name,
        version=row.version,
        family=row.family,
        engine=row.engine,
        capabilities=row.capabilities,
        vllm_eagle_head=row.vllm_eagle_head,
        memory_requirement_gb=row.memory_requirement_gb,
        ownership=row.ownership,
        status=row.status,
        created_at=row.created_at,
        metadata=row.metadata_json,
    )


def _deployment_from_row(row: DeploymentTable) -> DeploymentRecord:
    return DeploymentRecord(
        deployment_id=row.deployment_id,
        model_id=row.model_id,
        endpoint=row.endpoint,
        engine=row.engine,
        status=row.status,
        last_used=row.last_used,
        created_at=row.created_at,
        metadata=row.metadata_json,
    )


def _lifecycle_from_row(row: LifecycleTable) -> LifecycleRecord:
    return LifecycleRecord(
        deployment_id=row.deployment_id,
        state=row.state,
        last_transition=row.last_transition,
        idle_duration_seconds=row.idle_duration_seconds,
    )


def _telemetry_from_row(row: TelemetryTable) -> TelemetryEvent:
    return TelemetryEvent(
        request_id=row.request_id,
        deployment_id=row.deployment_id,
        model_name=row.model_name,
        latency_ms=row.latency_ms,
        e2e_latency_ms=row.e2e_latency_ms,
        ttft_ms=row.ttft_ms,
        tpot_ms=row.tpot_ms,
        itl_ms=row.itl_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        cache_hit=row.cache_hit,
        speculative_decoding=row.speculative_decoding,
        error=row.error,
        timestamp=row.timestamp,
        metadata=row.metadata_json,
    )


class InMemoryModelRepository(IModelRepository):
    """In-memory model repository for unit tests."""

    def __init__(self) -> None:
        self._models: dict[str, ModelRecord] = {}

    def save(self, model: ModelRecord) -> ModelRecord:
        self._models[model.id] = model
        return model

    def get(self, model_id: str) -> ModelRecord:
        try:
            return self._models[model_id]
        except KeyError as error:
            raise NotFoundError(f"Model not found: {model_id}") from error

    def list(self) -> list[ModelRecord]:
        return list(self._models.values())


class InMemoryDeploymentRepository(IDeploymentRepository):
    """In-memory deployment repository for unit tests."""

    def __init__(self) -> None:
        self._deployments: dict[str, DeploymentRecord] = {}

    def save(self, deployment: DeploymentRecord) -> DeploymentRecord:
        self._deployments[deployment.deployment_id] = deployment
        return deployment

    def get(self, deployment_id: str) -> DeploymentRecord:
        try:
            return self._deployments[deployment_id]
        except KeyError as error:
            raise NotFoundError(f"Deployment not found: {deployment_id}") from error

    def list(self) -> list[DeploymentRecord]:
        return list(self._deployments.values())


class InMemoryLifecycleRepository(ILifecycleRepository):
    """In-memory lifecycle repository for unit tests."""

    def __init__(self) -> None:
        self._records: dict[str, LifecycleRecord] = {}

    def save(self, record: LifecycleRecord) -> LifecycleRecord:
        self._records[record.deployment_id] = record
        return record

    def get(self, deployment_id: str) -> LifecycleRecord | None:
        return self._records.get(deployment_id)

    def list(self) -> list[LifecycleRecord]:
        return list(self._records.values())


class InMemoryTelemetryRepository(ITelemetryRepository):
    """In-memory telemetry repository for unit tests."""

    def __init__(self) -> None:
        self._events: dict[str, TelemetryEvent] = {}

    def save(self, event: TelemetryEvent) -> TelemetryEvent:
        self._events[event.request_id] = event
        return event

    def list(self) -> list[TelemetryEvent]:
        return list(self._events.values())

    def snapshot(self) -> MetricsSnapshot:
        events = self.list()
        total_requests = len(events)
        total_errors = sum(1 for event in events if event.error)
        average_latency = sum(event.latency_ms for event in events) / total_requests if total_requests else 0.0
        average_e2e = sum(event.e2e_latency_ms for event in events) / total_requests if total_requests else 0.0
        average_ttft = sum(event.ttft_ms for event in events) / total_requests if total_requests else 0.0
        average_tpot = sum(event.tpot_ms for event in events) / total_requests if total_requests else 0.0
        average_itl = sum(event.itl_ms for event in events) / total_requests if total_requests else 0.0
        spec_count = sum(1 for event in events if event.speculative_decoding)
        latencies = sorted(event.latency_ms for event in events)
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        p99 = latencies[int(min(len(latencies) * 0.99, len(latencies) - 1))] if latencies else 0.0
        return MetricsSnapshot(
            total_requests=total_requests,
            total_errors=total_errors,
            average_latency_ms=average_latency,
            average_e2e_latency_ms=average_e2e,
            average_ttft_ms=average_ttft,
            average_tpot_ms=average_tpot,
            average_itl_ms=average_itl,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            requests_with_speculative_decoding=spec_count,
        )


class SQLAlchemyModelRepository(IModelRepository):
    """SQLAlchemy ORM-backed model repository."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, model: ModelRecord) -> ModelRecord:
        with self._session_factory() as session:
            row = session.get(ModelTable, model.id) or ModelTable(id=model.id)
            row.name = model.name
            row.version = model.version
            row.family = model.family
            row.engine = model.engine
            row.capabilities = [str(capability) for capability in model.capabilities]
            row.vllm_eagle_head = model.vllm_eagle_head
            row.memory_requirement_gb = model.memory_requirement_gb
            row.ownership = model.ownership
            row.status = str(model.status)
            row.created_at = model.created_at
            row.metadata_json = model.metadata
            session.add(row)
            session.commit()
            session.refresh(row)
            return _model_from_row(row)

    def get(self, model_id: str) -> ModelRecord:
        with self._session_factory() as session:
            row = session.get(ModelTable, model_id)
            if row is None:
                raise NotFoundError(f"Model not found: {model_id}")
            return _model_from_row(row)

    def list(self) -> list[ModelRecord]:
        with self._session_factory() as session:
            rows = session.scalars(select(ModelTable).order_by(ModelTable.created_at.asc())).all()
            return [_model_from_row(row) for row in rows]


class SQLAlchemyDeploymentRepository(IDeploymentRepository):
    """SQLAlchemy ORM-backed deployment repository."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, deployment: DeploymentRecord) -> DeploymentRecord:
        with self._session_factory() as session:
            row = session.get(DeploymentTable, deployment.deployment_id) or DeploymentTable(
                deployment_id=deployment.deployment_id
            )
            row.model_id = deployment.model_id
            row.endpoint = deployment.endpoint
            row.engine = deployment.engine
            row.status = str(deployment.status)
            row.last_used = deployment.last_used
            row.created_at = deployment.created_at
            row.metadata_json = deployment.metadata
            session.add(row)
            session.commit()
            session.refresh(row)
            return _deployment_from_row(row)

    def get(self, deployment_id: str) -> DeploymentRecord:
        with self._session_factory() as session:
            row = session.get(DeploymentTable, deployment_id)
            if row is None:
                raise NotFoundError(f"Deployment not found: {deployment_id}")
            return _deployment_from_row(row)

    def list(self) -> list[DeploymentRecord]:
        with self._session_factory() as session:
            rows = session.scalars(select(DeploymentTable).order_by(DeploymentTable.created_at.asc())).all()
            return [_deployment_from_row(row) for row in rows]


class SQLAlchemyLifecycleRepository(ILifecycleRepository):
    """SQLAlchemy ORM-backed lifecycle repository."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, record: LifecycleRecord) -> LifecycleRecord:
        with self._session_factory() as session:
            row = session.get(LifecycleTable, record.deployment_id) or LifecycleTable(deployment_id=record.deployment_id)
            row.state = str(record.state)
            row.last_transition = record.last_transition
            row.idle_duration_seconds = record.idle_duration_seconds
            session.add(row)
            session.commit()
            session.refresh(row)
            return _lifecycle_from_row(row)

    def get(self, deployment_id: str) -> LifecycleRecord | None:
        with self._session_factory() as session:
            row = session.get(LifecycleTable, deployment_id)
            return _lifecycle_from_row(row) if row else None

    def list(self) -> list[LifecycleRecord]:
        with self._session_factory() as session:
            rows = session.scalars(select(LifecycleTable).order_by(LifecycleTable.last_transition.asc())).all()
            return [_lifecycle_from_row(row) for row in rows]


class SQLAlchemyTelemetryRepository(ITelemetryRepository):
    """SQLAlchemy ORM-backed telemetry repository."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, event: TelemetryEvent) -> TelemetryEvent:
        with self._session_factory() as session:
            row = session.get(TelemetryTable, event.request_id) or TelemetryTable(request_id=event.request_id)
            row.deployment_id = event.deployment_id
            row.model_name = event.model_name
            row.latency_ms = event.latency_ms
            row.e2e_latency_ms = event.e2e_latency_ms
            row.ttft_ms = event.ttft_ms
            row.tpot_ms = event.tpot_ms
            row.itl_ms = event.itl_ms
            row.prompt_tokens = event.prompt_tokens
            row.completion_tokens = event.completion_tokens
            row.cache_hit = event.cache_hit
            row.speculative_decoding = event.speculative_decoding
            row.error = event.error
            row.timestamp = event.timestamp
            row.metadata_json = event.metadata
            session.add(row)
            session.commit()
            session.refresh(row)
            return _telemetry_from_row(row)

    def list(self) -> list[TelemetryEvent]:
        with self._session_factory() as session:
            rows = session.scalars(select(TelemetryTable).order_by(TelemetryTable.timestamp.asc())).all()
            return [_telemetry_from_row(row) for row in rows]

    def snapshot(self) -> MetricsSnapshot:
        with self._session_factory() as session:
            total_requests = session.scalar(select(func.count(TelemetryTable.request_id))) or 0
            total_errors = session.scalar(select(func.count(TelemetryTable.request_id)).where(TelemetryTable.error.is_not(None))) or 0
            average_latency = session.scalar(select(func.avg(TelemetryTable.latency_ms))) or 0.0
            average_e2e = session.scalar(select(func.avg(TelemetryTable.e2e_latency_ms))) or 0.0
            average_ttft = session.scalar(select(func.avg(TelemetryTable.ttft_ms))) or 0.0
            average_tpot = session.scalar(select(func.avg(TelemetryTable.tpot_ms))) or 0.0
            average_itl = session.scalar(select(func.avg(TelemetryTable.itl_ms))) or 0.0
            spec_count = session.scalar(select(func.count(TelemetryTable.request_id)).where(TelemetryTable.speculative_decoding.is_(True))) or 0
            return MetricsSnapshot(
                total_requests=int(total_requests),
                total_errors=int(total_errors),
                average_latency_ms=float(average_latency),
                average_e2e_latency_ms=float(average_e2e),
                average_ttft_ms=float(average_ttft),
                average_tpot_ms=float(average_tpot),
                average_itl_ms=float(average_itl),
                requests_with_speculative_decoding=int(spec_count),
                # p95/p99 computed at application level for SQL simplicity
            )


class SQLiteModelRepository(SQLAlchemyModelRepository):
    """SQLite-backed model repository."""


class SQLiteDeploymentRepository(SQLAlchemyDeploymentRepository):
    """SQLite-backed deployment repository."""


class SQLiteLifecycleRepository(SQLAlchemyLifecycleRepository):
    """SQLite-backed lifecycle repository."""


class SQLiteTelemetryRepository(SQLAlchemyTelemetryRepository):
    """SQLite-backed telemetry repository."""
