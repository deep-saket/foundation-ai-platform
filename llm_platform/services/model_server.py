# Here we create an instance of IModelServer defined in llm_platform/interfaces/model_server.py

from __future__ import annotations # Py evaluates type hints during runtime (Solve forward/circular ref)
import httpx
from llm_platform.interfaces.model_server import IModelServer # Rules for model server instances to follow
from llm_platform.schemas.gateway import ChatCompletionRequest # Pydantic structure for the payload

class VllmModelServer(IModelServer):
	"""Concrete inplementation of model server followig guidelines laid out by abstract base class IModelServer that communicates with vLLM"""

	def __init__(self):
		
		# self.base_url = base_url # default points to port 8001
		pass

	async def generate(self, deployment:object, request: ChatCompletionRequest) -> str:
		"""Sends the request payload over the interna loopback network to live vllm container"""
		
		target_address = deployment.endpoint
		url = f"{target_address}/v1/chat/completions" # following openapi formatting
		
		# Extract info from Pydantic request payload
		payload = {
			"model": request.model,
			"messages": [{"role": m.role, "content": m.content} for m in request.messages],
			"temperature": request.temperature or 0.7
		}
        
		if request.stream:
			payload["stream"] = True

		# Open up a network pipe, convert dict payload to json and sent POST request to url
		async with httpx.AsyncClient() as client:
			if request.stream:
				# Stream response directly back to the gateway router
				# (We must implement a streaming generator if the gateway supports it, but since it doesn't, we just consume it and return the full text to avoid crashing)
				response = await client.post(url, json=payload, timeout=60.0)
				# For now, just return non-streaming until gateway supports SSE
			else:
				response = await client.post(url, json=payload, timeout=60.0)

		if response.status_code == 200:
			json_data = response.json()
			return json_data["choices"][0]["message"]["content"] # Extract LLM's Natural Lang. response from the comlpex json it return
		else:
			raise RuntimeError(f"vLLM server error: {response.text}")

