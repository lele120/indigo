"""
Indigo MCP Server — Streamable HTTP transport.

This module composes two surfaces over the same FastMCP instance:

1. **Standard MCP Streamable HTTP** on ``POST /mcp`` (JSON-RPC 2.0 with SSE).
   This is what conformant MCP clients (Claude Desktop, Claude Code's
   ``claude mcp add --transport http``) expect. Implemented by mounting the
   Starlette app returned by ``FastMCP.http_app(transport='streamable-http')``.

2. **Legacy REST shim** on ``GET /tools`` and ``POST /call-tool`` for quick
   manual testing with ``curl``. These wrap the same tool implementations.

Both surfaces share a single Bearer-token gate driven by ``MCP_API_KEY``.
"""
import json
import os
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional

import structlog
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from server import mcp

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()

MCP_API_KEY = os.getenv("MCP_API_KEY", "")
REQUIRE_AUTH = bool(MCP_API_KEY)

# Build the Streamable HTTP sub-app once and reuse its lifespan. FastMCP's
# http_app registers its own startup/shutdown hooks that must run for the
# /mcp endpoint to function, so we chain them into FastAPI's lifespan.
mcp_http_app = mcp.http_app(transport="streamable-http", stateless_http=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_http_app.lifespan(mcp_http_app):
        yield


app = FastAPI(
    title="Indigo MCP Server",
    description="Document Intelligence MCP Server with Streamable HTTP transport",
    version="1.1.0",
    lifespan=lifespan,
)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_var.set(correlation_id)
        logger.info(
            "http_request_start",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "http_request_complete",
            correlation_id=correlation_id,
            status_code=response.status_code,
        )
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer auth gate. Applies to /mcp, /tools, /call-tool; leaves / and /health open."""

    PROTECTED_PREFIXES = ("/mcp", "/tools", "/call-tool")

    async def dispatch(self, request: Request, call_next):
        if REQUIRE_AUTH and any(request.url.path.startswith(p) for p in self.PROTECTED_PREFIXES):
            auth = request.headers.get("authorization", "")
            token = auth.replace("Bearer ", "").strip()
            if token != MCP_API_KEY:
                return JSONResponse(
                    {"error": "unauthorized", "message": "Missing or invalid Bearer token"},
                    status_code=401,
                )
        return await call_next(request)


app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


def verify_api_key(authorization: Optional[str] = Header(None)) -> bool:
    """Legacy helper kept for explicit per-endpoint use."""
    if not REQUIRE_AUTH:
        return True
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if token != MCP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/")
async def root():
    tools = await mcp.list_tools()
    return {
        "name": "Indigo MCP Server",
        "version": "1.1.0",
        "transport": "streamable-http",
        "mcp_endpoint": "/mcp",
        "tools_count": len(tools),
        "authentication": "required" if REQUIRE_AUTH else "optional",
    }


@app.get("/health")
async def health():
    tools = await mcp.list_tools()
    return {"status": "healthy", "tools_available": len(tools)}


# --- Legacy REST shim (kept for curl-based testing) -------------------------

@app.get("/tools")
async def list_tools_rest(authorization: Optional[str] = Header(None)):
    """List tools via a simple REST shape (non-MCP)."""
    verify_api_key(authorization)
    tools = await mcp.list_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": getattr(tool, "inputSchema", getattr(tool, "input_schema", {})),
            }
            for tool in tools
        ]
    }


@app.post("/call-tool")
async def call_tool_rest(request: Request, authorization: Optional[str] = Header(None)):
    """Call a tool via a REST shape (non-MCP). Body: {name, arguments}."""
    verify_api_key(authorization)
    body = await request.json()
    tool_name = body.get("name")
    arguments = body.get("arguments", {})
    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")

    try:
        result = await mcp.call_tool(tool_name, arguments)
        if hasattr(result, "content"):
            text_content = result.content[0].text if result.content else str(result)
        elif hasattr(result, "text"):
            text_content = result.text
        else:
            text_content = str(result)
        return {"content": [{"type": "text", "text": text_content}]}
    except Exception as e:
        logger.error(
            "mcp_tool_failed",
            tool=tool_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call-tool-stream")
async def call_tool_stream(request: Request, authorization: Optional[str] = Header(None)):
    """SSE streaming version of /call-tool (non-MCP)."""
    verify_api_key(authorization)
    body = await request.json()
    tool_name = body.get("name")
    arguments = body.get("arguments", {})
    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")

    async def event_generator():
        try:
            result = await mcp.call_tool(tool_name, arguments)
            if hasattr(result, "content"):
                text_content = result.content[0].text if result.content else str(result)
            elif hasattr(result, "text"):
                text_content = result.text
            else:
                text_content = str(result)
            yield f"data: {json.dumps({'type':'content','content':[{'type':'text','text':text_content}]})}\n\n"
            yield f"data: {json.dumps({'type':'complete'})}\n\n"
        except Exception as e:
            logger.error("mcp_stream_error", error=str(e))
            yield f"data: {json.dumps({'type':'error','error':str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Standard MCP Streamable HTTP transport ---------------------------------

# Mount after all explicit routes so /mcp is served by FastMCP's built-in
# JSON-RPC handler. The path inside mcp_http_app is already "/mcp".
app.mount("/", mcp_http_app)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    logger.info("starting_mcp_http_server", port=port, auth_required=REQUIRE_AUTH)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
