import asyncio
from datetime import datetime, timezone
import uuid

from llm_platform.bootstrap import PlatformApplicationBuilder
from llm_platform.schemas.enums import DeploymentStatus, ModelStatus
from llm_platform.schemas.registry import DeploymentRecord, ModelRecord
from llm_platform.schemas.routing import RouteRequest

async def test_router():
    # Build platform in memory
    builder = PlatformApplicationBuilder()
    app = builder.build_from_file("configs/platform.yaml")
    
    registry = app.registry
    router = app.router
    
    # 1. Create a model
    model_id = str(uuid.uuid4())
    model = ModelRecord(
        id=model_id,
        name="test-model",
        version="1.0",
        family="unknown",
        engine="fake",
        capabilities=["chat"],
        memory_requirement_gb=1,
        ownership="system",
        status=ModelStatus.REGISTERED,
        created_at=datetime.now(timezone.utc),
        metadata={}
    )
    # Hack for in-memory testing without DB setup
    try:
        registry._model_repository.save(model)
    except Exception:
        pass
    
    # 2. Create two READY deployments for load balancing
    dep1_id = str(uuid.uuid4())
    dep1 = DeploymentRecord(
        deployment_id=dep1_id,
        model_id=model_id,
        endpoint="http://dep1",
        engine="fake",
        status=DeploymentStatus.READY,
        created_at=datetime.now(timezone.utc),
        metadata={"container_name": "c1"}
    )
    registry.update_deployment(dep1)
    
    dep2_id = str(uuid.uuid4())
    dep2 = DeploymentRecord(
        deployment_id=dep2_id,
        model_id=model_id,
        endpoint="http://dep2",
        engine="fake",
        status=DeploymentStatus.READY,
        created_at=datetime.now(timezone.utc),
        metadata={"container_name": "c2"}
    )
    registry.update_deployment(dep2)
    
    # 3. Test Load Balancing
    print("--- Testing Load Balancing ---")
    counts = {"dep1": 0, "dep2": 0}
    
    # Manually fetch models/deployments since we hacked the repo
    models = [model]
    deployments = registry.list_deployments()
    
    for _ in range(10):
        decision = router.route(
            RouteRequest(capability="chat"),
            models=models,
            deployments=deployments,
            lifecycle_records=[]
        )
        if decision.deployment_id == dep1_id: counts["dep1"] += 1
        if decision.deployment_id == dep2_id: counts["dep2"] += 1
    
    print(f"Routed 10 requests: {counts}")
    
    # 4. Test Unloading & Cold Start
    print("\n--- Testing Scale-to-Zero and Cold Starts ---")
    await app.chat_service.unload_deployment(dep1_id)
    await app.chat_service.unload_deployment(dep2_id)
    
    d1 = registry.get_deployment(dep1_id)
    d2 = registry.get_deployment(dep2_id)
    print(f"Deployments after unload: Dep1={d1.status}, Dep2={d2.status}")
    
    decision = router.route(
        RouteRequest(capability="chat"),
        models=models,
        deployments=registry.list_deployments(),
        lifecycle_records=[]
    )
    
    print(f"Cold Start Route Decision: {decision}")
    print("Tests complete!")

if __name__ == "__main__":
    asyncio.run(test_router())
