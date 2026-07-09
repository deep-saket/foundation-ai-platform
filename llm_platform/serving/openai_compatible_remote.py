"""Remote OpenAI-compatible serving clients.

vLLM and TGI both expose OpenAI-compatible chat completion APIs. This module
provides a reusable client implementation that can back multiple platform model
server adapters while keeping all HTTP logic in one place.
"""

from __future__ import annotations

from typing import Any

import httpx

from llm_platform.interfaces.model_server import IModelServer
from llm_platform.schemas.config import OpenAICompatibleBackendConfig
from llm_platform.schemas.gateway import ChatCompletionRequest
from llm_platform.schemas.registry import DeploymentCreateRequest, DeploymentRecord, ModelRecord
from llm_platform.utils.errors import NotFoundError, ValidationError


class OpenAICompatibleRemoteModelServer(IModelServer):
    """Base class for remote OpenAI-compatible inference backends."""

    backend_name = "remote-openai-compatible"

    def __init__(self, config: OpenAICompatibleBackendConfig) -> None:
        """Initialize the remote model server.

        Args:
            config: Remote backend connectivity settings.
        """
        self._config = config

    def deploy(self, model: ModelRecord, request: DeploymentCreateRequest) -> DeploymentRecord:
        """Validate backend health and create a deployment record.

        Args:
            model: Registered model metadata.
            request: Deployment request including optional remote overrides.

        Returns:
            Ready deployment metadata for a remote server target.
        """
        base_url = self._resolve_base_url(request)
        remote_model_name = self._resolve_remote_model_name(model, request)
        self._check_health(base_url)
        return DeploymentRecord(
            model_id=model.id,
            endpoint=request.endpoint,
            engine=request.engine or model.engine,
            status="ready",
            metadata={
                **request.metadata,
                "base_url": base_url,
                "remote_model_name": remote_model_name,
                "implementation": self.backend_name,
            },
        )

    def unload(self, deployment_id: str) -> None:
        """Unload a remote deployment.

        Remote servers are treated as externally managed in this phase, so
        unload is currently a no-op.
        """
        del deployment_id

    def health(self) -> dict[str, str | list[str]]:
        """Return health metadata for the remote backend config."""
        status = "configured" if self._config.base_url else "unconfigured"
        return {"status": status, "backend": self.backend_name, "placements": ["remote"]}

    def generate(self, deployment: DeploymentRecord, request: ChatCompletionRequest) -> str:
        """Call the remote OpenAI-compatible chat completions endpoint."""
        base_url = str(deployment.metadata.get("base_url") or self._config.base_url or "")
        remote_model_name = deployment.metadata.get("remote_model_name")
        if not base_url or not remote_model_name:
            raise NotFoundError("Remote deployment is missing `base_url` or `remote_model_name` metadata.")
        payload: dict[str, Any] = {
            "model": remote_model_name,
            "messages": [message.model_dump() for message in request.messages],
            "stream": request.stream,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        payload.update(request.metadata.get("backend_payload", {}))

        with self._client(base_url) as client:
            response = client.post(self._config.chat_completions_path, json=payload)
            if not response.is_success:
                error_msg = response.text
                try:
                    error_msg = response.json().get("message", response.text)
                except Exception:
                    pass
                raise ValidationError(f"Backend rejected request: {error_msg}")
            body = response.json()
        try:
            return str(body["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise ValidationError(f"Unexpected OpenAI-compatible response payload from {self.backend_name}.") from error

    def _check_health(self, base_url: str) -> None:
        """Check remote backend health."""
        with self._client(base_url) as client:
            response = client.get(self._config.health_path)
            response.raise_for_status()

    def _resolve_base_url(self, request: DeploymentCreateRequest) -> str:
        """Resolve the remote API base URL from request or config."""
        base_url = request.metadata.get("base_url") or self._config.base_url
        if not base_url:
            raise ValidationError(f"{self.backend_name} requires a configured base_url.")
        return str(base_url).rstrip("/")

    def _resolve_remote_model_name(self, model: ModelRecord, request: DeploymentCreateRequest) -> str:
        """Resolve the model identifier used by the remote backend API."""
        candidate = (
            request.metadata.get("remote_model_name")
            or model.metadata.get("remote_model_name")
            or model.metadata.get("source_model_id")
            or self._config.default_remote_model
            or model.name
        )
        return str(candidate)

    def _client(self, base_url: str) -> httpx.Client:
        """Create an HTTP client for the remote backend."""
        return httpx.Client(
            base_url=base_url,
            timeout=self._config.request_timeout_seconds,
            headers={"Authorization": f"Bearer {self._config.api_key}"},
        )
