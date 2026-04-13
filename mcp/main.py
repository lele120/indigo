"""
Indigo MCP Server - HTTP Transport with SSE (Server-Sent Events)

FastAPI wrapper for MCP server with Streamable HTTP support.
"""
import os
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders
import structlog
import json
from contextvars import ContextVar
from server import mcp

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()

# Configuration
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
REQUIRE_AUTH = bool(MCP_API_KEY)

# Initialize FastAPI app
app = FastAPI(
    title="Indigo MCP Server",
    description="Document Intelligence MCP Server with Streamable HTTP transport",
    version="1.0.0",
)

# Correlation ID middleware
class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to each request"""

    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_var.set(correlation_id)

        # Log request start
        logger.info(
            "http_request_start",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Log request complete
        logger.info(
            "http_request_complete",
            correlation_id=correlation_id,
            status_code=response.status_code,
        )

        return response


# Add middleware
app.add_middleware(CorrelationIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


# Authentication middleware
def verify_api_key(authorization: Optional[str] = Header(None)) -> bool:
    """Verify API key from Authorization header"""
    if not REQUIRE_AUTH:
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Support both "Bearer <key>" and "<key>" formats
    token = authorization.replace("Bearer ", "").strip()

    if token != MCP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


@app.get("/")
async def root():
    """Root endpoint"""
    tools = await mcp.list_tools()
    return {
        "name": "Indigo MCP Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "tools_count": len(tools),
        "authentication": "required" if REQUIRE_AUTH else "optional",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    tools = await mcp.list_tools()
    return {
        "status": "healthy",
        "tools_available": len(tools),
    }


@app.get("/tools")
async def list_tools(authorization: Optional[str] = Header(None)):
    """List all available MCP tools"""
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
async def call_tool(request: Request, authorization: Optional[str] = Header(None)):
    """
    Call an MCP tool with Streamable HTTP (SSE)

    Request body:
    {
        "name": "tool_name",
        "arguments": {...}
    }
    """
    verify_api_key(authorization)

    try:
        body = await request.json()
        tool_name = body.get("name")
        arguments = body.get("arguments", {})

        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing 'name' field")

        correlation_id = correlation_id_var.get()
        logger.info(
            "mcp_tool_called",
            correlation_id=correlation_id,
            tool=tool_name,
            arguments=arguments,
        )

        # Call the tool
        result = await mcp.call_tool(tool_name, arguments)

        logger.info(
            "mcp_tool_success",
            correlation_id=correlation_id,
            tool=tool_name,
        )

        # Extract text content from ToolResult
        if hasattr(result, 'content'):
            # ToolResult with content list
            text_content = result.content[0].text if result.content else str(result)
        elif hasattr(result, 'text'):
            text_content = result.text
        else:
            text_content = str(result)

        return {
            "content": [
                {
                    "type": "text",
                    "text": text_content,
                }
            ]
        }

    except Exception as e:
        correlation_id = correlation_id_var.get()
        logger.error(
            "mcp_tool_failed",
            correlation_id=correlation_id,
            tool=body.get("name", "unknown"),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call-tool-stream")
async def call_tool_stream(request: Request, authorization: Optional[str] = Header(None)):
    """
    Call an MCP tool with streaming response (SSE)

    This endpoint returns Server-Sent Events for streaming responses.
    """
    verify_api_key(authorization)

    try:
        body = await request.json()
        tool_name = body.get("name")
        arguments = body.get("arguments", {})

        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing 'name' field")

        correlation_id = correlation_id_var.get()
        logger.info(
            "mcp_tool_stream_called",
            correlation_id=correlation_id,
            tool=tool_name,
            arguments=arguments,
        )

        async def event_generator():
            """Generate SSE events"""
            try:
                # Call the tool
                result = await mcp.call_tool(tool_name, arguments)

                # Extract text content from ToolResult
                if hasattr(result, 'content'):
                    text_content = result.content[0].text if result.content else str(result)
                elif hasattr(result, 'text'):
                    text_content = result.text
                else:
                    text_content = str(result)

                # Send result as SSE
                event_data = {
                    "type": "content",
                    "content": [
                        {
                            "type": "text",
                            "text": text_content,
                        }
                    ]
                }

                yield f"data: {json.dumps(event_data)}\n\n"

                # Send completion event
                completion_data = {
                    "type": "complete",
                }
                yield f"data: {json.dumps(completion_data)}\n\n"

            except Exception as e:
                logger.error("mcp_stream_error", error=str(e))
                error_data = {
                    "type": "error",
                    "error": str(e),
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error("mcp_stream_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))

    logger.info("starting_mcp_http_server", port=port, auth_required=REQUIRE_AUTH)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
