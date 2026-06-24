"""
RAG System MCP Server - Streamable HTTP Transport
Exposes RAG query functionality as MCP tools via HTTP

This MCP server provides:
- search_knowledge_base: Query knowledge base with natural language

Run this file to start the MCP server with HTTP transport
"""
import asyncio
import sys
import os
from typing import Optional
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import Tool, TextContent

from app.core.config import settings
from app.pipelines import query_pipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Create MCP server instance
mcp_server = Server("rag-system-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_knowledge_base",
            description="""Search the RAG knowledge base and generate an answer.

Flow:
1. Embed query text to vector
2. Hybrid search (Elasticsearch + Milvus) with kb_id filtering
3. Rerank results by relevance
4. Assemble context with source annotations
5. Generate answer using LLM

Supports multi-tenant knowledge base isolation with kb_id.

Returns:
- answer: Generated answer based on retrieved context
- context_chunks: Number of context chunks used
- kb_ids: Knowledge base IDs that were queried
- reranked_results: Top relevant documents with sources""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User query text in natural language"
                    },
                    "kb_id": {
                        "type": "string",
                        "description": "Knowledge base ID for data isolation. Can be single or comma-separated multiple (e.g., 'kb_finance' or 'kb_finance,kb_hr')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of search results to retrieve (optional, uses default from config if not provided)",
                        "default": None
                    },
                    "rerank_top_n": {
                        "type": "integer",
                        "description": "Number of reranked results to use for context (optional, uses default from config if not provided)",
                        "default": None
                    },
                    "rerank_threshold": {
                        "type": "number",
                        "description": "Minimum relevance score threshold (0-1) for filtering results (optional, uses default from config if not provided)",
                        "default": None
                    },
                    "temperature": {
                        "type": "number",
                        "description": "LLM temperature for answer generation (optional, uses default from config if not provided)",
                        "default": None
                    }
                },
                "required": ["query", "kb_id"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    if name != "search_knowledge_base":
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]

    # Extract arguments
    query = arguments.get("query")
    kb_id = arguments.get("kb_id")
    top_k = arguments.get("top_k")
    rerank_top_n = arguments.get("rerank_top_n")
    rerank_threshold = arguments.get("rerank_threshold")
    temperature = arguments.get("temperature")

    # Validate required arguments
    if not query:
        return [TextContent(
            type="text",
            text="Error: 'query' is required"
        )]

    if not kb_id:
        return [TextContent(
            type="text",
            text="Error: 'kb_id' is required"
        )]

    logger.info(f"MCP Tool called: search_knowledge_base(query='{query[:50]}...', kb_id='{kb_id}')")

    try:
        # Call the query pipeline
        result = await query_pipeline.run(
            query=query,
            kb_id=kb_id,
            top_k=top_k,
            rerank_top_n=rerank_top_n,
            rerank_threshold=rerank_threshold,
            temperature=temperature
        )

        # Format response
        response_parts = [
            f"## Answer\n{result.answer}\n",
            f"## Metadata",
            f"- Query: {result.query}",
            f"- Knowledge Bases: {result.kb_ids}",
            f"- Context Chunks Used: {result.context_chunks}"
        ]

        # Add usage info if available
        if result.usage:
            response_parts.append(f"- Token Usage: {result.usage.get('total_tokens', 'N/A')} tokens")

        # Add source information
        if result.reranked_results:
            response_parts.append("\n## Top Sources")
            for i, r in enumerate(result.reranked_results[:5], 1):
                response_parts.append(
                    f"{i}. [{r.kb_id}] {r.doc_name} (relevance: {r.relevance_score:.4f})"
                )

        response_text = "\n".join(response_parts)

        return [TextContent(
            type="text",
            text=response_text
        )]

    except Exception as e:
        logger.error(f"MCP tool error: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error processing query: {str(e)}"
        )]


async def handle_mcp_request(request: Request) -> Response:
    """Handle MCP HTTP requests"""
    try:
        # Create transport for each request
        transport = StreamableHTTPServerTransport(
            mcp_session_id=None,
            is_json_response_enabled=False
        )

        # Handle the request through the transport
        response = await transport.handle_request(request, mcp_server)

        return response

    except Exception as e:
        logger.error(f"Error handling MCP request: {str(e)}", exc_info=True)
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


async def health_check(request: Request) -> Response:
    """Health check endpoint"""
    return Response(
        content='{"status": "healthy", "service": "rag-system-mcp"}',
        media_type="application/json"
    )


# Create Starlette app
app = Starlette(
    routes=[
        Route("/mcp", handle_mcp_request, methods=["GET", "POST"]),
        Route("/health", health_check, methods=["GET"]),
    ]
)


def main():
    """Main entry point - run MCP HTTP server"""
    import uvicorn

    # Get port from environment or use default
    port = int(os.getenv("MCP_PORT", "8022"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    logger.info(f"Starting RAG System MCP Server v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"MCP HTTP server listening on {host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp")

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=settings.LOG_LEVEL.lower()
        )
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
