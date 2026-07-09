"""FastAPI routers."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from llm_platform.bootstrap import PlatformApplication
from llm_platform.gateway.dependencies import get_application, get_chat_service
from llm_platform.services.chat import ChatService
from llm_platform.schemas.gateway import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    DeploymentResponse,
    ModelDeployRequest,
    ModelRegisterRequest,
    ModelResponse,
    ModelsResponse,
    ModelUnloadRequest,
    ModelValidateRequest,
    OpenAIChatChoice,
    OpenAIChatCompletionResponse,
    OpenAIChatMessage,
    ValidationResponse,
)
from llm_platform.utils.errors import NotFoundError, PlatformError, RoutingError, ValidationError


router = APIRouter()
v1_router = APIRouter(prefix="/v1")


def _translate_error(error: PlatformError) -> HTTPException:
    if isinstance(error, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (RoutingError, ValidationError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    application: PlatformApplication = Depends(get_application),
) -> ChatCompletionResponse:
    try:
        return await application.chat_service.chat(payload)
    except PlatformError as error:
        raise _translate_error(error) from error


@v1_router.post("/chat/completions", response_model=OpenAIChatCompletionResponse)
async def create_openai_chat_completion(
    payload: ChatCompletionRequest,
    application: PlatformApplication = Depends(get_application),
) -> OpenAIChatCompletionResponse:
    try:
        response = await application.chat_service.chat(payload)
    except PlatformError as error:
        raise _translate_error(error) from error
    return OpenAIChatCompletionResponse(
        id=response.request_id,
        created=int(datetime.now(timezone.utc).timestamp()),
        model=response.route.model_id,
        choices=[
            OpenAIChatChoice(
                index=0,
                message=OpenAIChatMessage(role="assistant", content=response.message),
            )
        ],
    )


@router.post("/models/register", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def register_model(
    payload: ModelRegisterRequest,
    application: PlatformApplication = Depends(get_application),
) -> ModelResponse:
    try:
        model = application.model_management_service.register_model(payload)
    except PlatformError as error:
        raise _translate_error(error) from error
    return ModelResponse(model=model)


@v1_router.post("/models/register", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def register_model_v1(
    payload: ModelRegisterRequest,
    application: PlatformApplication = Depends(get_application),
) -> ModelResponse:
    return register_model(payload, application)


@router.post("/models/deploy", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
def deploy_model(
    payload: ModelDeployRequest,
    application: PlatformApplication = Depends(get_application),
) -> DeploymentResponse:
    try:
        deployment = application.model_management_service.deploy_model(payload)
    except PlatformError as error:
        raise _translate_error(error) from error
    return DeploymentResponse(deployment=deployment)


@v1_router.post("/models/deploy", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
def deploy_model_v1(
    payload: ModelDeployRequest,
    application: PlatformApplication = Depends(get_application),
) -> DeploymentResponse:
    return deploy_model(payload, application)


@router.post("/models/unload", response_model=DeploymentResponse)
def unload_model(
    payload: ModelUnloadRequest,
    application: PlatformApplication = Depends(get_application),
) -> DeploymentResponse:
    try:
        deployment = application.model_management_service.unload_model(payload.deployment_id)
    except PlatformError as error:
        raise _translate_error(error) from error
    return DeploymentResponse(deployment=deployment)


@v1_router.post("/models/unload", response_model=DeploymentResponse)
def unload_model_v1(
    payload: ModelUnloadRequest,
    application: PlatformApplication = Depends(get_application),
) -> DeploymentResponse:
    return unload_model(payload, application)


@router.post("/models/validate", response_model=ValidationResponse)
def validate_model(
    payload: ModelValidateRequest,
    application: PlatformApplication = Depends(get_application),
) -> ValidationResponse:
    try:
        report = application.compatibility_checker.inspect_huggingface_repo(
            payload.hf_repo,
            revision=payload.revision,
        )
    except PlatformError as error:
        raise _translate_error(error) from error
    return ValidationResponse(report=report)


@v1_router.post("/models/validate", response_model=ValidationResponse)
def validate_model_v1(
    payload: ModelValidateRequest,
    application: PlatformApplication = Depends(get_application),
) -> ValidationResponse:
    return validate_model(payload, application)


@router.get("/models", response_model=ModelsResponse)
def list_models(application: PlatformApplication = Depends(get_application)) -> ModelsResponse:
    return ModelsResponse(models=application.model_management_service.list_models())


@v1_router.get("/models", response_model=ModelsResponse)
def list_models_v1(application: PlatformApplication = Depends(get_application)) -> ModelsResponse:
    return ModelsResponse(models=application.model_management_service.list_models())


# ── Model Capabilities Endpoint ──────────────────────────────────────

@v1_router.get("/models/capabilities")
def list_capabilities(
    application: PlatformApplication = Depends(get_application),
) -> dict[str, object]:
    """Returns all registered capabilities and which models support each."""
    models = application.model_management_service.list_models()
    
    capability_map: dict[str, list[dict[str, object]]] = {}
    for model in models:
        for cap in model.capabilities:
            cap_str = str(cap)
            if cap_str not in capability_map:
                capability_map[cap_str] = []
            capability_map[cap_str].append({
                "model_id": model.id,
                "model_name": model.name,
                "family": model.family,
                "memory_requirement_gb": model.memory_requirement_gb,
                "vllm_eagle_head": model.vllm_eagle_head,
                "status": str(model.status),
            })
    
    return {
        "capabilities": capability_map,
        "total_models": len(models),
    }


@router.get("/models/capabilities")
def list_capabilities_root(
    application: PlatformApplication = Depends(get_application),
) -> dict[str, object]:
    return list_capabilities(application)


@router.get("/models/{model_id}", response_model=ModelResponse)
def get_model(
    model_id: str,
    application: PlatformApplication = Depends(get_application),
) -> ModelResponse:
    try:
        model = application.model_management_service.get_model(model_id)
    except PlatformError as error:
        raise _translate_error(error) from error
    return ModelResponse(model=model)


@v1_router.get("/models/{model_id}", response_model=ModelResponse)
def get_model_v1(
    model_id: str,
    application: PlatformApplication = Depends(get_application),
) -> ModelResponse:
    return get_model(model_id, application)


@v1_router.get("/models/{model_id}/status", response_model=ModelResponse)
def get_model_status_v1(
    model_id: str,
    application: PlatformApplication = Depends(get_application),
) -> ModelResponse:
    return get_model(model_id, application)


@router.get("/health")
def get_health(application: PlatformApplication = Depends(get_application)) -> dict[str, object]:
    return application.health_service.health()


@router.get("/metrics")
def get_metrics(application: PlatformApplication = Depends(get_application)) -> dict[str, object]:
    return application.telemetry_provider.snapshot().model_dump()


@v1_router.get("/health")
def get_health_v1(application: PlatformApplication = Depends(get_application)) -> dict[str, object]:
    return application.health_service.health()

# Code for POST request
@v1_router.post("/chat/completions/direct", response_model=ChatCompletionResponse)
async def create_direct_chat_completion(
	request: ChatCompletionRequest,
	chat_service: ChatService = Depends(get_chat_service),
) -> ChatCompletionResponse:
	"""response_model=ChatCompletionResponse guarantees returned object follows this layout."""

	try:
		response = await chat_service.chat(request)
		return response
	except PlatformError as error:
		raise _translate_error(error) from error


# ── GPU Status Endpoint ──────────────────────────────────────────────

@v1_router.get("/gpu/status")
def get_gpu_status(
    application: PlatformApplication = Depends(get_application),
) -> dict[str, object]:
    """Returns current GPU VRAM allocation and available headroom."""
    tracker = application.gpu_tracker
    return {
        "total_vram_gb": tracker.total_vram_gb,
        "allocated_vram_gb": tracker.allocated_vram_gb,
        "available_vram_gb": tracker.available_vram_gb,
        "allocations": tracker.allocations,
    }


@router.get("/gpu/status")
def get_gpu_status_root(
    application: PlatformApplication = Depends(get_application),
) -> dict[str, object]:
    return get_gpu_status(application)


# ── Inference Metrics Endpoint (TPOT, TTFT, E2EL, ITL) ──────────────

@v1_router.get("/inference/metrics")
def get_inference_metrics(
    application: PlatformApplication = Depends(get_application),
    limit: int = 50,
) -> dict[str, object]:
    """Returns inference telemetry with TPOT, TTFT, E2EL, ITL breakdowns.

    - **TPOT**: Time Per Output Token (ms)
    - **TTFT**: Time To First Token (ms)
    - **E2EL**: End-to-End Latency (ms)
    - **ITL**: Inter-Token Latency (ms)
    """
    snapshot = application.telemetry_provider.snapshot()
    
    # Get recent events for per-request breakdown
    events = []
    try:
        raw_events = application.telemetry_provider._repository.list()
        for event in raw_events[-limit:]:
            events.append({
                "request_id": event.request_id,
                "model_name": event.model_name,
                "e2e_latency_ms": round(event.e2e_latency_ms, 2),
                "ttft_ms": round(event.ttft_ms, 2),
                "tpot_ms": round(event.tpot_ms, 2),
                "itl_ms": round(event.itl_ms, 2),
                "completion_tokens": event.completion_tokens,
                "speculative_decoding": event.speculative_decoding,
                "timestamp": event.timestamp.isoformat(),
                "metadata": event.metadata,
            })
    except AttributeError:
        # NoOpTelemetryProvider has no _repository
        pass

    return {
        "summary": {
            "total_requests": snapshot.total_requests,
            "total_errors": snapshot.total_errors,
            "average_e2e_latency_ms": round(snapshot.average_e2e_latency_ms, 2),
            "average_ttft_ms": round(snapshot.average_ttft_ms, 2),
            "average_tpot_ms": round(snapshot.average_tpot_ms, 2),
            "average_itl_ms": round(snapshot.average_itl_ms, 2),
            "p95_latency_ms": round(snapshot.p95_latency_ms, 2),
            "p99_latency_ms": round(snapshot.p99_latency_ms, 2),
            "requests_with_speculative_decoding": snapshot.requests_with_speculative_decoding,
        },
        "recent_requests": events,
    }


@router.get("/inference/metrics")
def get_inference_metrics_root(
    application: PlatformApplication = Depends(get_application),
    limit: int = 50,
) -> dict[str, object]:
    return get_inference_metrics(application, limit)

