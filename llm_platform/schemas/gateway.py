"""Gateway API schemas."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from llm_platform.schemas.enums import Capability
from llm_platform.schemas.registry import DeploymentCreateRequest, DeploymentRecord, ModelRecord, ModelRegistrationRequest
from llm_platform.schemas.routing import RouteDecision
from llm_platform.schemas.validation import ValidationReport


class ChatMessage(BaseModel):
    """Single chat message in OpenAI-compatible shape."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """Unified chat completion request used by the gateway and services."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    capability: Capability | str = Capability.CHAT
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    password: str | None = None
    huggingface_id: str | None = None


class ChatCompletionResponse(BaseModel):
    """Internal chat completion response with routing metadata."""

    request_id: str
    status: str
    route: RouteDecision
    message: str


class OpenAIChatMessage(BaseModel):
    """OpenAI-compatible assistant message."""

    role: str = "assistant"
    content: str


class OpenAIChatChoice(BaseModel):
    """OpenAI-compatible chat completion choice."""

    index: int
    message: OpenAIChatMessage
    finish_reason: str = "stop"


class OpenAIChatUsage(BaseModel):
    """OpenAI-compatible usage block."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChatChoice]
    usage: OpenAIChatUsage = Field(default_factory=OpenAIChatUsage)


class ModelRegisterRequest(ModelRegistrationRequest):
    pass


class ModelDeployRequest(DeploymentCreateRequest):
    pass


class ModelUnloadRequest(BaseModel):
    deployment_id: str


class ModelValidateRequest(BaseModel):
    """Request payload for Hugging Face model validation."""

    hf_repo: str
    revision: str | None = None


class ModelResponse(BaseModel):
    model: ModelRecord


class ModelsResponse(BaseModel):
    models: list[ModelRecord]


class DeploymentResponse(BaseModel):
    deployment: DeploymentRecord


class ValidationResponse(BaseModel):
    """Response payload for compatibility validation."""

    report: ValidationReport
