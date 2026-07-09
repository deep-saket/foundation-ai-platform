# Model Lifecycle Management & Advanced Routing

This document explains the architectural changes made to introduce a **Scale-to-Zero Lifecycle Worker** and **Advanced Routing** (Load Balancing and Cold Starts) into the Foundation AI Platform.

---

## 1. The Scale-to-Zero Background Worker

### What was there before:
Previously, the platform was static. Once a user requested a model and the vLLM Docker container spun up, that container would run indefinitely, consuming precious GPU VRAM forever until the server was manually restarted.

### What we added:
We created an asynchronous background task (`lifecycle_worker.py`) that constantly monitors the `LifecycleRecord` of every active deployment. We also updated the main FastAPI application (`app.py`) to launch this worker using a `lifespan` hook.

### What it does:
Every 10 seconds, the worker:
1. Iterates through all currently `READY` deployments.
2. Increments their `idle_duration_seconds`.
3. Passes the record to the `LifecycleManager` to see if the state should shift (e.g., from `HOT` to `WARM` to `COLD`).
4. If a model crosses the threshold into `COLD`, the worker forcefully unloads the vLLM Docker container to free up the GPU.

### Code Snippets

**The Background Loop (`llm_platform/services/lifecycle_worker.py`):**
```python
async def run_lifecycle_loop(app: FastAPI):
    # Wait for the application state to initialize
    await asyncio.sleep(5)
    platform = app.state.platform_application

    while True:
        deployments = platform.registry.list_deployments()
        for deployment in deployments:
            if deployment.status != DeploymentStatus.READY:
                continue
                
            record = platform.registry.get_lifecycle(deployment.deployment_id)
            if not record:
                continue
                
            # Increment idle time
            record.idle_duration_seconds += 10
            
            # Reconcile state
            updated_record = platform.lifecycle_manager.reconcile(record)
            platform.registry.upsert_lifecycle(updated_record)
            
            # Scale-to-zero trigger
            if updated_record.state == LifecycleState.COLD:
                print(f"[Lifecycle Worker] Deployment {deployment.deployment_id} transitioned to COLD. Unloading...")
                await platform.chat_service.unload_deployment(deployment.deployment_id)
                
        await asyncio.sleep(10)
```

**Wiring it into FastAPI (`llm_platform/gateway/app.py`):**
```python
from llm_platform.services.lifecycle_worker import run_lifecycle_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background worker when the server boots
    worker_task = asyncio.create_task(run_lifecycle_loop(app))
    yield
    # Safely shut it down when the server closes
    worker_task.cancel()
```

---

## 2. Advanced Routing (Load Balancing & Cold Starts)

### What was there before:
The `CapabilityRouter` was extremely basic. It took the list of deployments, looked for the first one that matched the requested capability, and returned it. It had no concept of multiple containers (load balancing) or what to do if all containers were currently shut off (cold starts).

### What we added:
We rewrote the routing algorithm in `router.py` and added a new `requires_cold_start` flag to the `RouteDecision` schema. 

### What it does:
The new router first tries to find all `READY` containers that support the request. If it finds more than one, it uses `random.choice()` to distribute the load across them (Load Balancing). 
If it finds *zero* `READY` containers, but it *does* find an `UNLOADED` container (a model that was downloaded but killed by the lifecycle worker), it routes to the dead container but flags it with `requires_cold_start = True`.

### Code Snippets

**The New Router (`llm_platform/routing/router.py`):**
```python
class CapabilityRouter(IRouter):
    def route(self, request: RouteRequest, models: list[ModelRecord], deployments: list[DeploymentRecord], ...) -> RouteDecision:
        # 1. Find all models that match the capability
        capable_model_ids = {m.id for m in models if request.capability in m.capabilities}
        
        # 2. Separate deployments into READY and UNLOADED
        ready_deps = []
        unloaded_deps = []
        for d in deployments:
            if d.model_id in capable_model_ids:
                if d.status == DeploymentStatus.READY:
                    ready_deps.append(d)
                elif d.status == DeploymentStatus.UNLOADED:
                    unloaded_deps.append(d)
                    
        # 3. Load Balancing: Pick a random READY deployment
        if ready_deps:
            chosen = random.choice(ready_deps)
            return RouteDecision(
                deployment_id=chosen.deployment_id,
                model_id=chosen.model_id,
                endpoint=chosen.endpoint,
                requires_cold_start=False
            )
            
        # 4. Cold Start Fallback: Pick an UNLOADED deployment and flag it
        if unloaded_deps:
            chosen = random.choice(unloaded_deps)
            return RouteDecision(
                deployment_id=chosen.deployment_id,
                model_id=chosen.model_id,
                endpoint=chosen.endpoint,
                requires_cold_start=True
            )
```

---

## 3. The Orchestrator Bridge

### What was there before:
The `ChatService` expected every route decision to point to a fully functional container. It had no logic to handle restarting dead containers or cleaning them up.

### What we added:
We updated the `chat()` method in `chat.py` to intercept the new `requires_cold_start` flag. We also added an `unload_deployment` helper method that uses the Docker SDK to forcefully kill containers.

### What it does:
When a request comes in and the router says `requires_cold_start=True`, the `ChatService` pauses the request, runs the `deploy_vllm_container` logic to boot the container back up from the SSD cache, and *then* forwards the user's prompt. 

### Code Snippets

**Intercepting Cold Starts (`llm_platform/services/chat.py`):**
```python
        # Get the routing decision
        route = self._router.route(...)
        
        deployment = self._registry.get_deployment(route.deployment_id)
        model = self._registry.get_model(route.model_id)
        
        # If the router flagged a cold start, spin the Docker container back up!
        if route.requires_cold_start:
            logger.info(f"Cold start required for model {model.name}. Deploying container...")
            deployment = await self.deploy_vllm_container(model, deployment)
            route.endpoint = deployment.endpoint

        # Initialize or Reset the lifecycle timer so it doesn't get immediately killed
        lifecycle = self._registry.get_lifecycle(route.deployment_id)
        if lifecycle:
            self._registry.upsert_lifecycle(self._lifecycle_manager.touch(lifecycle))
        else:
            new_record = self._lifecycle_manager.initialize(deployment)
            self._registry.upsert_lifecycle(new_record)
```

**Destroying Containers (`llm_platform/services/chat.py`):**
```python
    async def unload_deployment(self, deployment_id: str) -> None:
        """Unload a deployment by stopping and removing its container."""
        deployment = self._registry.get_deployment(deployment_id)
        container_name = deployment.metadata.get("container_name")
        
        if container_name:
            client = docker.from_env()
            try:
                container = client.containers.get(container_name)
                container.remove(force=True)  # Kill the container
            except docker.errors.NotFound:
                pass
                
        deployment.status = DeploymentStatus.UNLOADED
        self._registry.update_deployment(deployment)
```
