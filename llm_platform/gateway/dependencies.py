"""Gateway dependency helpers."""

from __future__ import annotations
from fastapi import Request
from llm_platform.bootstrap import PlatformApplication

# Some additional imports
from fastapi import Depends
from llm_platform.services.chat import ChatService
from llm_platform.services.model_server import VllmModelServer
"""
When the gateway application starts (server process initializes) 
bootstrap.py script executes to instantiate the PlatformApplication 
toolbox, which bundles essential components like config, 
deployment_repository, and plugin_manager. 
This toolbox is pinned into the application's global memory space 
by being stored in request.app.state.platform_application. 
The get_application function acts as a retriever that looks into 
this shared memory space to hand the toolbox reference (not a copy!)
to any service that requests it. By storing this object centrally, 
the system ensures that every incoming request can instantly grab 
a reference to this toolkit without needing to re-initialize 
heavy resources repeatedly.
"""
def get_application(request: Request) -> PlatformApplication:
    return request.app.state.platform_application

"""
When client sends HTTP message over n/w, fastAPI parses it into
an organized Python object wrapper whose template is the Request 
class. request: Request instructs to catch HTTP message data, 
package it in Request template and assign it to request variable.

In fastAPI Depends() is a dependency injection tool, i.e. it acts as 
an automated retreiver. when get_chat_service is triggered, 
Depends(...) automatically runs the get_application and assigns the 
memory reference of Platform Application toolbox to app_state.

The function get_chat_service is triggered dynamically by FastAPI itself, exclusively 
in response to the "event" of a client's network message arriving at 
the gateway.
"""
async def get_chat_service(
	request: Request,
	app_state: PlatformApplication = Depends(get_application)
) -> ChatService: 

	"""Fetches a ready ChatService instance"""

	return app_state.chat_service
