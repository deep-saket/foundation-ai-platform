"""Shared enumerations used across the platform."""

from __future__ import annotations

# from enum import StrEnum
from enum import Enum

# This is a 'polyfill'. It gives Python 3.10 (Brev) 
# the same powers as 3.11.
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return self.value

class Capability(StrEnum):
    CHAT = "chat"
    REASONING = "reasoning"
    TOOL_CALLING = "tool_calling"
    SUMMARIZATION = "summarization"
    CODE_GENERATION = "code_generation"
    EMBEDDING = "embedding"
    EVALUATION = "evaluation"
    CLASSIFICATION = "classification"


class ModelStatus(StrEnum):
    REGISTERED = "registered"
    DEPLOYED = "deployed"
    DISABLED = "disabled"
    FAILED = "failed"


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    UNLOADED = "unloaded"
    FAILED = "failed"


class LifecycleState(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    FAILED = "FAILED"


class EngineType(StrEnum):
    VLLM = "vllm"
    HUGGINGFACE_TRANSFORMERS = "huggingface-transformers"
    TENSORRT_LLM = "tensorrt-llm"
    SGLANG = "sglang"
    TGI = "tgi"
    NIM = "nim"
    EXTERNAL_API = "external-api"
