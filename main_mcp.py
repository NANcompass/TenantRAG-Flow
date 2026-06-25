"""
RAG System MCP Server - FastMCP with Streamable HTTP Transport
Exposes RAG query functionality as MCP tools via HTTP

This MCP server provides:
- search_knowledge_base: Query knowledge base with natural language

Run this file to start the MCP server with HTTP transport
"""
import asyncio
import sys
import os
from typing import Optional
import uvicorn
from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.pipelines import query_pipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Get configuration from environment
host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "8022"))

# Create FastMCP instance with JSON response enabled (recommended)
mcp = FastMCP(
    "rag-system-mcp",
    json_response=True  # Recommended for Dify compatibility
)

# Configure server host and port
mcp.settings.host = host
mcp.settings.port = port

# Disable DNS rebinding protection to allow connections from any host
# This is necessary for Dify platform compatibility
mcp.settings.transport_security.enable_dns_rebinding_protection = False
mcp.settings.transport_security.allowed_hosts = ["*"]
mcp.settings.transport_security.allowed_origins = ["*"]


@mcp.tool()
async def search_knowledge_base(
    query: str,
    kb_id: str,
    top_k: Optional[int] = None,
    rerank_top_n: Optional[int] = None,
    rerank_threshold: Optional[float] = None,
    temperature: Optional[float] = None
) -> str:
    """Search the RAG knowledge base and generate an answer.

    Flow:
    1. Embed query text to vector
    2. Hybrid search (Elasticsearch + Milvus) with kb_id filtering
    3. Rerank results by relevance
    4. Assemble context with source annotations
    5. Generate answer using LLM

    Supports multi-tenant knowledge base isolation with kb_id.

    Args:
        query: User query text in natural language
        kb_id: Knowledge base ID for data isolation. Can be single or comma-separated multiple (e.g., 'kb_finance' or 'kb_finance,kb_hr')
        top_k: Number of search results to retrieve (optional, uses default from config if not provided)
        rerank_top_n: Number of reranked results to use for context (optional, uses default from config if not provided)
        rerank_threshold: Minimum relevance score threshold (0-1) for filtering results (optional, uses default from config if not provided)
        temperature: LLM temperature for answer generation (optional, uses default from config if not provided)

    Returns:
        Answer with metadata and top sources
    """
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
            f"{result.answer}\n"
            # f"## Answer\n{result.answer}\n",
            # f"## Metadata",
            # f"- Query: {result.query}",
            # f"- Knowledge Bases: {result.kb_ids}",
            # f"- Context Chunks Used: {result.context_chunks}"
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

        return "\n".join(response_parts)

    except Exception as e:
        logger.error(f"MCP tool error: {str(e)}", exc_info=True)
        return f"Error processing query: {str(e)}"


def main():
    """Main entry point - run MCP HTTP server"""
    logger.info(f"Starting RAG System MCP Server v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"MCP HTTP server listening on {host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp")

    try:
        # Get the Starlette app from FastMCP
        app = mcp.streamable_http_app()

        # Run with uvicorn using configured settings
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=settings.LOG_LEVEL.lower()
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()