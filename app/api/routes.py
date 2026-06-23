"""
API Routes for RAG System V2
Supports multi-tenant knowledge base isolation with kb_id
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.models import (
    IngestionResult,
    QueryResult,
)
from app.pipelines import ingestion_pipeline, query_pipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Create routers
ingestion_router = APIRouter(prefix="/ingest", tags=["Ingestion"])
query_router = APIRouter(prefix="/query", tags=["Query"])


# ============================================
# Request Models V2
# ============================================

class SearchRequest(BaseModel):
    """Request body for search endpoint V2"""
    query: str = Field(description="User query text")
    kb_id: str = Field(description="Knowledge base ID (single or comma-separated multiple)")
    top_k: Optional[int] = Field(default=None, description="Number of search results")
    rerank_top_n: Optional[int] = Field(default=None, description="Number of reranked results to use")
    rerank_threshold: Optional[float] = Field(default=None, description="Minimum relevance score")
    temperature: Optional[float] = Field(default=None, description="LLM temperature")


class IngestRequest(BaseModel):
    """Request body for ingest endpoint V2"""
    path: str = Field(description="File or folder path to ingest")
    kb_id: str = Field(description="Knowledge base ID for data isolation")
    chunk_size: Optional[int] = Field(default=None, description="Target chunk size")
    chunk_overlap: Optional[int] = Field(default=None, description="Chunk overlap")
    mode: Optional[str] = Field(default=None, description="Chunking mode: general or parent_child")
    semantic_split: Optional[bool] = Field(default=None, description="Enable semantic splitting")
    preserve_hierarchy: Optional[bool] = Field(default=None, description="Preserve heading hierarchy")


# ============================================
# Ingestion Pipeline Endpoints V2
# ============================================

@ingestion_router.post("/file", response_model=IngestionResult)
async def ingest_file(request: IngestRequest):
    """
    Ingest a file or folder into the RAG system V2 with kb_id support

    Flow:
    1. Chunking documents
    2. Generating embeddings (batch processing, max 100 per batch)
    3. Storing in MySQL/ES/Milvus with kb_id (max 100 chunks per request)

    V2 Features:
    - Multi-tenant data isolation with kb_id
    - Automatic Upsert (no need to delete before updating)
    - Batch processing to prevent service overload

    Args:
        request: IngestRequest with path, kb_id and optional parameters
            - path: File or folder path to ingest (required)
            - kb_id: Knowledge base ID for data isolation (required)
            - chunk_size: Target chunk size (default from .env)
            - chunk_overlap: Chunk overlap (default from .env)
            - mode: Chunking mode - "general" or "parent_child"
            - semantic_split: Enable semantic splitting
            - preserve_hierarchy: Preserve heading hierarchy

    Returns:
        IngestionResult with statistics and kb_id

    Example:
        POST /ingest/file
        {
            "path": "/data/documents/finance",
            "kb_id": "kb_finance"
        }
    """
    logger.info(f"Received ingestion request V2: path={request.path}, kb_id={request.kb_id}")

    try:
        result = await ingestion_pipeline.run(
            path=request.path,
            kb_id=request.kb_id,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            mode=request.mode,
            semantic_split=request.semantic_split,
            preserve_hierarchy=request.preserve_hierarchy
        )
        return result
    except Exception as e:
        logger.error(f"Ingestion failed for kb_id={request.kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Query Pipeline Endpoints V2
# ============================================

@query_router.post("/search", response_model=QueryResult)
async def search(request: SearchRequest):
    """
    Search the knowledge base and generate an answer V2 with kb_id support

    Flow:
    1. Embed query
    2. Hybrid search (ES + Milvus) with kb_id filtering
    3. Rerank results (standardize ES and Milvus scores)
    4. Assemble context with source annotations [来源: kb_id / 文档: doc_name]
    5. Generate answer with LLM

    V2 Features:
    - Multi-tenant search with kb_id (single or comma-separated multiple)
    - Standardized reranking to handle score differences
    - Source attribution in context and response

    Args:
        request: SearchRequest with query, kb_id and optional parameters
            - query: User query text (required)
            - kb_id: Knowledge base ID - single or comma-separated multiple
                     e.g., "kb_finance" or "kb_finance,kb_hr" (required)
            - top_k: Number of search results (default from .env)
            - rerank_top_n: Number of reranked results to use (default from .env)
            - rerank_threshold: Minimum relevance score (default from .env)
            - temperature: LLM temperature (default from .env)

    Returns:
        QueryResult with answer, source attribution, and metadata

    Example:
        POST /query/search
        {
            "query": "什么是差旅报销标准?",
            "kb_id": "kb_finance,kb_hr"
        }
    """
    logger.info(f"Received query request V2: query={request.query[:50]}..., kb_id={request.kb_id}")

    try:
        result = await query_pipeline.run(
            query=request.query,
            kb_id=request.kb_id,
            top_k=request.top_k,
            rerank_top_n=request.rerank_top_n,
            rerank_threshold=request.rerank_threshold,
            temperature=request.temperature
        )
        return result
    except Exception as e:
        logger.error(f"Query failed for kb_id={request.kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
