"""Chat request orchestration.

This module contains the application service responsible for request routing,
lightweight lifecycle updates, model-server invocation, and telemetry emission.
The service intentionally avoids transport and persistence details so it can be
tested in isolation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from time import perf_counter
from typing import TYPE_CHECKING

_global_boot_lock = asyncio.Lock()

from llm_platform.interfaces.lifecycle import ILifecycleManager
from llm_platform.interfaces.model_server import IModelServer
from llm_platform.interfaces.registry import IRegistry
from llm_platform.interfaces.router import IRouter
from llm_platform.interfaces.telemetry import ITelemetryProvider
from llm_platform.schemas.gateway import ChatCompletionRequest, ChatCompletionResponse
from llm_platform.schemas.routing import RouteRequest
from llm_platform.schemas.telemetry import TelemetryEvent
from llm_platform.utils.errors import NotFoundError

if TYPE_CHECKING:
    from llm_platform.services.gpu_tracker import GPUResourceTracker
    from llm_platform.services.concurrency import ConcurrencyTracker

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        registry: IRegistry,
        router: IRouter,
        lifecycle_manager: ILifecycleManager,
        telemetry_provider: ITelemetryProvider,
        model_server: IModelServer,
        compatibility_checker: "ICompatibilityChecker | None" = None,
        model_cache_dir: str = "./data/model-cache",
        gpu_tracker: "GPUResourceTracker | None" = None,
        concurrency_tracker: "ConcurrencyTracker | None" = None,
        num_speculative_tokens: int = 5,
    ) -> None:
        self._registry = registry
        self._router = router
        self._lifecycle_manager = lifecycle_manager
        self._telemetry_provider = telemetry_provider
        self._model_server = model_server
        self._compatibility_checker = compatibility_checker
        self._model_cache_dir = model_cache_dir
        self._gpu_tracker = gpu_tracker
        self._concurrency_tracker = concurrency_tracker
        self._num_speculative_tokens = num_speculative_tokens
        # Per-model lock: prevents concurrent cold-start races
        self._cold_start_locks: dict[str, asyncio.Lock] = {}
        # Global routing lock: ensures atomic decisions for concurrent requests
        self._routing_lock = asyncio.Lock()
        
        # Port reservation lock to prevent concurrent cold-start port collisions
        self._port_lock = asyncio.Lock()
        self._reserved_ports: set[int] = set()

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Asynchronously handles the entire chat request workflow."""
        started = perf_counter()
        
        # 1. Resolve or Onboard Model (if specific model requested)
        models = self._registry.list_models()
        model_record = None
        
        if request.model:
            for m in models:
                if m.id == request.model or m.name == request.model:
                    model_record = m
                    break
                    
            if not model_record:
                password = request.password or request.metadata.get("password")
                if password == "dhruv":
                    hf_repo = request.huggingface_id or request.model
                    if not hf_repo:
                        raise NotFoundError("Hugging Face repository ID must be provided for onboarding.")
                    model_record = await self.onboard_model(hf_repo)
                    models = self._registry.list_models()
                else:
                    raise NotFoundError(f"Requested model was not found in registry: {request.model}")

        deployments = self._registry.list_deployments()

        # 3. Dynamic Router and Text Generation
        async with self._routing_lock:
            lifecycle_records = [
                record 
                for record in (self._registry.get_lifecycle(d.deployment_id) for d in deployments) 
                if record
            ]
            
            route = self._router.route(
                RouteRequest(
                    capability=request.capability,
                    preferred_model_id=model_record.id if model_record else None,
                    metadata={**request.metadata, "_registry": self._registry},
                ),
                models=models,
                deployments=deployments,
                lifecycle_records=lifecycle_records,
            )
            
            # Immediately reserve GPU to prevent subsequent concurrent requests from over-subscribing it
            if route.requires_cold_start or route.requires_new_instance:
                if self._gpu_tracker and route.deployment_id:
                    # The GPU tracker's `allocate` safely overwrites if called multiple times for the same deployment ID
                    model_for_alloc = next((m for m in models if m.id == route.model_id), None)
                    if model_for_alloc:
                        self._gpu_tracker.allocate(route.deployment_id, model_for_alloc.memory_requirement_gb)
        
        # ── Handle Eviction ──────────────────────────────────────────
        if route.evict_deployment_id:
            logger.info(f"Evicting idle deployment {route.evict_deployment_id} to free GPU space")
            await self.unload_deployment(route.evict_deployment_id)
            if self._gpu_tracker:
                self._gpu_tracker.release(route.evict_deployment_id)

        # ── Handle Cold Start or New Instance ────────────────────────
        deployment = self._registry.get_deployment(route.deployment_id) if route.deployment_id else None
        model = self._registry.get_model(route.model_id)
        
        if route.requires_cold_start or route.requires_new_instance:
            # Per-model lock: only one cold start runs at a time per model.
            # Concurrent requests wait here; once the first finishes and the
            # deployment is READY, subsequent requests skip deploy_vllm_container.
            if route.model_id not in self._cold_start_locks:
                self._cold_start_locks[route.model_id] = asyncio.Lock()
            async with self._cold_start_locks[route.model_id]:
                # Re-fetch deployment inside the lock — another request may
                # have already completed the cold start while we were waiting.
                deployment = self._registry.get_deployment(route.deployment_id) if route.deployment_id else None
                from llm_platform.schemas.enums import DeploymentStatus
                if deployment and deployment.status == DeploymentStatus.READY:
                    logger.info(f"Cold start already completed by another request for {model.name}, reusing.")
                    route.endpoint = deployment.endpoint
                elif deployment and deployment.status == DeploymentStatus.FAILED:
                    logger.warning(f"Deployment for {model.name} is FAILED. Falling back to a busy deployment.")
                    deployment = self._find_fallback_deployment(request.capability)
                    if deployment is None:
                        from llm_platform.utils.errors import RoutingError
                        raise RoutingError(f"No running deployment available for capability: {request.capability}")
                    route.deployment_id = deployment.deployment_id
                    route.endpoint = deployment.endpoint
                else:
                    logger.info(
                        f"{'Cold start' if route.requires_cold_start else 'New instance'} "
                        f"required for model {model.name}. Deploying container..."
                    )
                    try:
                        deployment = await self.deploy_vllm_container(model, deployment)
                        route.endpoint = deployment.endpoint
                        route.deployment_id = deployment.deployment_id
                    except Exception as cold_start_error:
                        # Release GPU allocation if cold start failed
                        if self._gpu_tracker and deployment:
                            self._gpu_tracker.release(deployment.deployment_id)
                        
                        # Mark as FAILED so the router permanently skips this deployment.
                        logger.error(f"Cold start failed for {model.name}: {cold_start_error}. Marking FAILED and falling back.")
                        if deployment:
                            deployment.status = DeploymentStatus.FAILED
                            self._registry.update_deployment(deployment)
                        # Fall back: queue at any already-running READY deployment.
                        deployment = self._find_fallback_deployment(request.capability)
                        if deployment is None:
                            from llm_platform.utils.errors import RoutingError
                            raise RoutingError(
                                f"Cold start failed for {model.name} and no fallback deployment is available "
                                f"for capability: {request.capability}"
                            ) from cold_start_error
                        route.deployment_id = deployment.deployment_id
                        route.endpoint = deployment.endpoint


        # ── Lifecycle Touch ──────────────────────────────────────────
        lifecycle = self._registry.get_lifecycle(route.deployment_id)
        if lifecycle:
            self._registry.upsert_lifecycle(self._lifecycle_manager.touch(lifecycle))
        else:
            new_record = self._lifecycle_manager.initialize(deployment)
            self._registry.upsert_lifecycle(new_record)
            
        # ── Generate with Inference Timing ───────────────────────────
        import inspect
        from fastapi.concurrency import run_in_threadpool

        inference_start = perf_counter()
        
        # Track active requests
        if self._concurrency_tracker and route.deployment_id:
            self._concurrency_tracker.increment(route.deployment_id)
            
        try:
            if inspect.iscoroutinefunction(self._model_server.generate):
                message = await self._model_server.generate(deployment, request)
            else:
                message = await run_in_threadpool(self._model_server.generate, deployment, request)
        finally:
            if self._concurrency_tracker and route.deployment_id:
                self._concurrency_tracker.decrement(route.deployment_id)
                
        inference_end = perf_counter()

        # ── Compute Metrics ──────────────────────────────────────────
        e2e_latency_ms = (perf_counter() - started) * 1000.0
        inference_time_ms = (inference_end - inference_start) * 1000.0
        
        # TTFT: For non-streaming, we approximate as time-to-inference-complete
        # In a streaming setup, this would be time to first chunk
        ttft_ms = (inference_start - started) * 1000.0  # Time spent before inference = routing + cold start overhead
        
        # Estimate token-level metrics from response
        # These are approximations — vLLM returns usage info in its response
        completion_tokens = max(len(message.split()) if message else 0, 1)
        tpot_ms = inference_time_ms / completion_tokens if completion_tokens > 0 else 0.0
        itl_ms = tpot_ms  # For non-streaming, ITL ≈ TPOT
        
        latency_ms = e2e_latency_ms  # backward compat
        
        self._telemetry_provider.emit(
            TelemetryEvent(
                request_id=request.request_id,
                deployment_id=route.deployment_id,
                model_name=model.name,
                latency_ms=latency_ms,
                e2e_latency_ms=e2e_latency_ms,
                ttft_ms=ttft_ms,
                tpot_ms=tpot_ms,
                itl_ms=itl_ms,
                completion_tokens=completion_tokens,
                speculative_decoding=bool(model.vllm_eagle_head),
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "capability": str(request.capability),
                    "inference_time_ms": inference_time_ms,
                    "cold_start": route.requires_cold_start,
                    "new_instance": route.requires_new_instance,
                    "evicted": route.evict_deployment_id,
                },
            )
        )
        
        return ChatCompletionResponse(
            request_id=request.request_id,
            status="accepted",
            route=route,
            message=message,
        )

    def _find_fallback_deployment(self, capability: str) -> "DeploymentRecord | None":
        """Return any READY deployment whose model supports the given capability.

        Used when a cold start fails or the GPU is full: instead of erroring,
        we queue the request at whichever model is already running.
        Picks the deployment with the fewest active requests (Power of Two Choices
        degrades to min-load when only one option exists).
        """
        from llm_platform.schemas.enums import DeploymentStatus

        deployments = self._registry.list_deployments()
        models = {m.id: m for m in self._registry.list_models()}

        candidates = []
        for dep in deployments:
            if dep.status != DeploymentStatus.READY:
                continue
            model = models.get(dep.model_id)
            if model and capability in [str(c) for c in model.capabilities]:
                active = 0
                if self._concurrency_tracker:
                    active = self._concurrency_tracker.get_active_requests(dep.deployment_id)
                candidates.append((active, dep))

        if not candidates:
            return None
        # Return the deployment with the lowest current load
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    async def unload_deployment(self, deployment_id: str) -> None:

        """Unload a deployment by stopping and removing its container."""
        import docker
        from llm_platform.schemas.enums import DeploymentStatus
        
        deployment = self._registry.get_deployment(deployment_id)
        if not deployment:
            return
            
        container_name = deployment.metadata.get("container_name")
        if container_name:
            client = docker.from_env()
            try:
                container = client.containers.get(container_name)
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
                
        deployment.status = DeploymentStatus.UNLOADED
        self._registry.update_deployment(deployment)

    async def onboard_model(self, hf_repo: str, eagle_head_repo: str | None = None) -> 'ModelRecord':
        from llm_platform.utils.errors import ValidationError
        if not self._compatibility_checker:
            raise ValidationError("Compatibility checker is not configured on ChatService.")
            
        report = self._compatibility_checker.inspect_huggingface_repo(hf_repo)
        if report.recommended_backend not in ["vllm", "huggingface-transformers"]:
            raise ValidationError(
                f"Model {hf_repo} is not compatible with the platform. Recommended backend: {report.recommended_backend}"
            )
            
        # Download main model weights asynchronously in thread pool
        from huggingface_hub import snapshot_download
        from fastapi.concurrency import run_in_threadpool
        await run_in_threadpool(
            snapshot_download,
            repo_id=hf_repo,
            cache_dir=self._model_cache_dir
        )

        # Download EAGLE head if specified
        if eagle_head_repo:
            logger.info(f"[EAGLE] Downloading speculative decoding head: {eagle_head_repo}")
            await run_in_threadpool(
                snapshot_download,
                repo_id=eagle_head_repo,
                cache_dir=self._model_cache_dir
            )
        
        family = "generic"
        if report.architecture:
            arch_lower = report.architecture.lower()
            if "qwen" in arch_lower:
                family = "qwen"
            elif "llama" in arch_lower:
                family = "llama"
            elif "mistral" in arch_lower:
                family = "mistral"
            elif "deepseek" in arch_lower:
                family = "deepseek"
                
        # Determine capability based on model identity
        hf_repo_lower = hf_repo.lower()
        capabilities = ["chat"]
        if "phi-3" in hf_repo_lower:
            capabilities = ["math"]
        elif "deepseek" in hf_repo_lower:
            capabilities = ["reasoning"]
        elif "qwen" in hf_repo_lower:
            capabilities = ["summarization"]

        # Register Model
        from llm_platform.schemas.registry import ModelRegistrationRequest
        registration_request = ModelRegistrationRequest(
            name=hf_repo,
            version="1.0",
            family=family,
            engine="vllm",
            capabilities=capabilities,
            vllm_eagle_head=eagle_head_repo,
            memory_requirement_gb=math.ceil(report.estimated_gpu_memory_gb or 16),
            ownership="user",
            metadata={
                "architecture": report.architecture or "unknown",
                "estimated_gpu_memory_gb": report.estimated_gpu_memory_gb or 0.0,
                "max_context_length": report.max_context_length,
            }
        )
        model_record = self._registry.register_model(registration_request)
        
        # Register deployment as PENDING
        from llm_platform.schemas.registry import DeploymentRecord
        from llm_platform.schemas.enums import DeploymentStatus
        import uuid
        
        deployment_record = DeploymentRecord(
            deployment_id=str(uuid.uuid4()),
            model_id=model_record.id,
            endpoint="http://localhost:pending",
            engine="vllm",
            status=DeploymentStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata={}
        )
        self._registry.update_deployment(deployment_record)
        
        return model_record

    async def deploy_vllm_container(
        self, 
        model_record: 'ModelRecord', 
        existing_deployment: 'DeploymentRecord | None'
    ) -> 'DeploymentRecord':
        import socket
        import docker
        from fastapi.concurrency import run_in_threadpool
        from pathlib import Path
        from llm_platform.schemas.enums import DeploymentStatus
        from llm_platform.schemas.registry import DeploymentRecord
        import uuid
        
        async with _global_boot_lock:
            # Re-check DB inside lock in case a concurrent task just finished booting it
            if existing_deployment:
                refreshed = self._registry.get_deployment(existing_deployment.deployment_id)
                if refreshed.status == DeploymentStatus.READY:
                    return refreshed
                    
            # Find free port starting at 8002 atomically
            port = 8002
            async with self._port_lock:
                while True:
                    if port not in self._reserved_ports:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            try:
                                s.bind(("127.0.0.1", port))
                                self._reserved_ports.add(port)
                                break
                            except OSError:
                                pass
                    port += 1
                    
            sanitized_name = model_record.name.replace("/", "-").replace(".", "-").replace(":", "-").lower()
            container_name = f"vllm-{sanitized_name}"
            # vLLM's --gpu-memory-utilization allocates an absolute fraction of the physical GPU exclusively for this process.
            # To ensure models can coexist without crashing (OOM), we just divide the model's required memory by the total GPU memory.
            # We guarantee at least 2.5GB or 1.5x the estimated requirement, whichever is higher.
            total_hardware_vram = self._gpu_tracker.total_vram_gb if self._gpu_tracker else 24.0
            safe_memory_gb = max(2.5, model_record.memory_requirement_gb * 1.5)
            ratio = safe_memory_gb / total_hardware_vram
            
            # Just ensure it doesn't exceed 95% of the total GPU. No more static 22% minimums!
            utilization = min(0.95, ratio)
            
            def run_docker():
                client = docker.from_env()
                try:
                    existing = client.containers.get(container_name)
                    # If it's already running, don't kill it!
                    if existing.status == "running":
                        cmd = existing.attrs.get("Config", {}).get("Cmd", [])
                        try:
                            port_idx = cmd.index("--port")
                            actual_port = int(cmd[port_idx + 1])
                            return existing, actual_port
                        except (ValueError, IndexError):
                            pass
                        return existing, None
                    existing.remove(force=True)
                except docker.errors.NotFound:
                    pass
                    
                device_request = docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
                
                # Ensure the cache directory exists before mounting
                host_cache_path = Path(self._model_cache_dir).resolve()
                host_cache_path.mkdir(parents=True, exist_ok=True)
                host_path = str(host_cache_path)
                
                # Mount it exactly where the huggingface hub inside the container expects it
                container_path = "/root/.cache/huggingface/hub"
                
                command = f"--model {model_record.name} --port {port} --host 0.0.0.0 --gpu-memory-utilization {utilization:.2f}"
                
                # Determine the absolute maximum context window.
                # We enforce a ceiling of 4096 to prevent KV cache OOM on massive context models (like DeepSeek).
                max_ctx = model_record.metadata.get("max_context_length")
                if max_ctx:
                    capped_len = min(4096, max_ctx)
                else:
                    # Fallback for models already registered in the DB without max_context_length
                    capped_len = 2048 if "tinyllama" in model_record.name.lower() else 4096
                    
                command += f" --max-model-len {capped_len} --trust-remote-code"
                
                # EAGLE Speculative Decoding
                if model_record.vllm_eagle_head:
                    spec_config = {
                        "method": "eagle",
                        "model": model_record.vllm_eagle_head,
                        "num_speculative_tokens": self._num_speculative_tokens,
                    }
                    command += f" --speculative-config '{json.dumps(spec_config)}'"
                    logger.info(
                        f"[EAGLE] Enabling speculative decoding with head: {model_record.vllm_eagle_head} "
                        f"({self._num_speculative_tokens} tokens)"
                    )
                
                return client.containers.run(
                    image="vllm/vllm-openai:v0.22.1-cu129",
                    command=command,
                    name=container_name,
                    detach=True,
                    network_mode="host",
                    volumes={
                        host_path: {
                            'bind': container_path,
                            'mode': 'rw'
                        }
                    },
                    device_requests=[device_request]
                )
            
            def cleanup_docker():
                client = docker.from_env()
                try:
                    c = client.containers.get(container_name)
                    logs = c.logs(tail=50).decode('utf-8', errors='ignore')
                    logger.error(f"========== FATAL: CONTAINER {container_name} CRASHED OR TIMED OUT ==========\n{logs}")
                    c.remove(force=True)
                except docker.errors.NotFound:
                    pass
                
            try:
                result = await run_in_threadpool(run_docker)
                if isinstance(result, tuple):
                    container, actual_port = result
                    if actual_port and actual_port != port:
                        self._reserved_ports.discard(port)
                        port = actual_port
                        self._reserved_ports.add(port)
                else:
                    container = result
                
                # Poll readiness health check
                import httpx
                import asyncio
                url = f"http://127.0.0.1:{port}/v1/models"
                ready = False
                async with httpx.AsyncClient() as client:
                    for _ in range(360):  # 30 minutes (360 * 5s)
                        try:
                            response = await client.get(url, timeout=2.0)
                            if response.status_code == 200:
                                ready = True
                                break
                        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
                            pass
                        await asyncio.sleep(5)
                        
                if not ready:
                    await run_in_threadpool(cleanup_docker)
                    raise RuntimeError(f"vLLM container for {model_record.name} failed to become healthy on port {port}")
            except Exception:
                self._reserved_ports.discard(port)
                raise
            
        endpoint = f"http://127.0.0.1:{port}"
        
        if existing_deployment:
            existing_deployment.endpoint = endpoint
            existing_deployment.status = DeploymentStatus.READY
            new_metadata = dict(existing_deployment.metadata)
            new_metadata["port"] = port
            new_metadata["container_name"] = container_name
            new_metadata["base_url"] = endpoint
            new_metadata["remote_model_name"] = model_record.name
            new_metadata["eagle_head"] = model_record.vllm_eagle_head
            existing_deployment.metadata = new_metadata
            deployment_record = self._registry.update_deployment(existing_deployment)
        else:
            deployment_record = DeploymentRecord(
                deployment_id=str(uuid.uuid4()),
                model_id=model_record.id,
                endpoint=endpoint,
                engine="vllm",
                status=DeploymentStatus.READY,
                created_at=datetime.now(timezone.utc),
                metadata={
                    "port": port, 
                    "container_name": container_name,
                    "base_url": endpoint,
                    "remote_model_name": model_record.name,
                    "eagle_head": model_record.vllm_eagle_head,
                }
            )
            self._registry.update_deployment(deployment_record)
            
        return deployment_record

    async def prewarm_capabilities(self, capabilities: list[str]) -> None:
        """Eagerly loads one model for each requested capability at startup.
        
        The prewarmed deployments are marked as 'is_permanent' so they bypass
        the scale-to-zero lifecycle worker and GPU eviction.
        """
        import uuid
        from llm_platform.schemas.registry import DeploymentRecord
        from llm_platform.schemas.enums import DeploymentStatus
        
        logger.info(f"Pre-warming baseline models for capabilities: {capabilities}")
        models = self._registry.list_models()
        
        # CLEAR old ghost deployments from previous runs so router doesn't hit dead ports
        try:
            repo = getattr(self._registry, "_deployment_repository", None)
            if repo and hasattr(repo, "_session_factory"):
                from sqlalchemy import delete
                from llm_platform.database.models import DeploymentTable, LifecycleTable
                with repo._session_factory() as session:
                    session.execute(delete(LifecycleTable))
                    session.execute(delete(DeploymentTable))
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to clear ghost deployments: {e}")
        
        for capability in capabilities:
            # Find the best model for this capability
            eligible_models = [m for m in models if capability in m.capabilities]
            
            if not eligible_models:
                logger.warning(f"No models found for capability '{capability}', attempting to auto-onboard default...")
                default_repos = {
                    "chat": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
                    "summarization": "Qwen/Qwen2.5-1.5B-Instruct",
                    "math": "microsoft/Phi-3-mini-4k-instruct"
                }
                repo = default_repos.get(capability)
                if repo:
                    try:
                        selected_model = await self.onboard_model(repo)
                        # Add it to the local models list so it doesn't get missed later
                        models.append(selected_model)
                    except Exception as e:
                        logger.error(f"Failed to auto-onboard {repo}: {e}")
                        continue
                else:
                    logger.error(f"No default repo configured for capability '{capability}'.")
                    continue
            else:
                # Prefer models with more capabilities
                eligible_models.sort(key=lambda m: len(m.capabilities), reverse=True)
                selected_model = eligible_models[0]
            
            logger.info(f"Pre-warming {selected_model.name} for capability '{capability}'...")
            
            # Create a PENDING deployment record flagged as permanent
            dep_id = str(uuid.uuid4())
            deployment = DeploymentRecord(
                deployment_id=dep_id,
                model_id=selected_model.id,
                endpoint="",
                engine="vllm",
                status=DeploymentStatus.PENDING,
                metadata={"is_permanent": True}
            )
            self._registry.update_deployment(deployment)
            
            # Reserve VRAM
            if self._gpu_tracker:
                self._gpu_tracker.allocate(dep_id, selected_model.memory_requirement_gb)
                
            # Create lifecycle record
            if self._lifecycle_manager:
                new_record = self._lifecycle_manager.initialize(deployment)
                self._registry.upsert_lifecycle(new_record)
                
            # Deploy it (this will block until it is READY because we await it)
            try:
                if selected_model.id not in self._cold_start_locks:
                    self._cold_start_locks[selected_model.id] = asyncio.Lock()
                    
                async with self._cold_start_locks[selected_model.id]:
                    # deploy_vllm_container handles the actual docker run and updates the status to READY
                    ready_deployment = await self.deploy_vllm_container(selected_model, deployment)
                    
                    # Ensure is_permanent is preserved
                    ready_deployment.metadata["is_permanent"] = True
                    self._registry.update_deployment(ready_deployment)
                    logger.info(f"Successfully pre-warmed baseline model: {selected_model.name}")
            except Exception as e:
                logger.error(f"Failed to pre-warm {selected_model.name}: {e}")
                deployment.status = DeploymentStatus.FAILED
                self._registry.update_deployment(deployment)
                if self._gpu_tracker:
                    self._gpu_tracker.release(dep_id)
