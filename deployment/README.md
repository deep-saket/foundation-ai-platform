# `deployment/` — Deployment Artifacts

Contains Docker and deployment-related files for containerizing and deploying the platform.

---

## Files

### `Dockerfile.gateway`

Dockerfile for building the FastAPI gateway container image.

- **Base Image:** Python slim
- **Copies:** Platform source code and dependencies
- **Exposes:** The gateway port (default 8000)
- **Entrypoint:** Runs the FastAPI gateway application via `uvicorn`

---

## Usage

```bash
# Build the gateway image
docker build -f deployment/Dockerfile.gateway -t foundation-ai-gateway .

# Run the gateway container
docker run -p 8000:8000 foundation-ai-gateway
```

The gateway can also be run as part of the full stack using the root `docker-compose.yml`, which orchestrates the gateway alongside the vLLM serving container.
