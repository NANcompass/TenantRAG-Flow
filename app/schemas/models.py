"""
Data Schemas / Models for RAG System
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ============================================
# Chunking Service Schemas
# ============================================

class ChunkRequest(BaseModel):
    """Request for document chunking"""
    path: str = Field(description="File or folder path to chunk")
    mode: Optional[str] = Field(default="general", description="Chunking mode: general/parent_child")
    chunk_size: Optional[int] = Field(default=1024, description="Target chunk size in characters")
    chunk_overlap: Optional[int] = Field(default=50, description="Chunk overlap in characters")
    semantic_split: Optional[bool] = Field(default=True, description="Enable semantic splitting")
    preserve_hierarchy: Optional[bool] = Field(default=True, description="Preserve heading hierarchy")
    parent_chunk_size: Optional[int] = Field(default=1500, description="Parent chunk size")
    child_chunk_size: Optional[int] = Field(default=200, description="Child chunk size")
    child_chunk_overlap: Optional[int] = Field(default=20, description="Child chunk overlap")


class ChunkMetadata(BaseModel):
    """Metadata for a single chunk"""
    heading: Optional[str] = Field(default=None, description="Heading text")
    heading_level: Optional[int] = Field(default=None, description="Heading level (1-6)")
    type: Optional[str] = Field(default=None, description="Chunk type: semantic/text/etc")


class Chunk(BaseModel):
    """Single chunk from chunking service"""
    id: str = Field(description="Chunk unique ID")
    content: str = Field(description="Chunk text content")
    index: int = Field(description="Chunk index in document")
    start_pos: Optional[int] = Field(default=None, description="Start position in source")
    end_pos: Optional[int] = Field(default=None, description="End position in source")
    metadata: Optional[ChunkMetadata] = Field(default=None, description="Chunk metadata")
    char_count: Optional[int] = Field(default=None, description="Character count")
    word_count: Optional[int] = Field(default=None, description="Word count")


class ChunkStatistics(BaseModel):
    """Statistics for a chunked document"""
    source: Optional[str] = Field(default=None, description="Source file name")
    total_chars: Optional[int] = Field(default=None, description="Total characters")
    total_lines: Optional[int] = Field(default=None, description="Total lines")
    avg_chunk_size: Optional[float] = Field(default=None, description="Average chunk size")
    mode: Optional[str] = Field(default=None, description="Chunking mode used")


class ChunkResult(BaseModel):
    """Chunking result for a single file"""
    mode: Optional[str] = Field(default=None, description="Chunking mode")
    total_chunks: int = Field(description="Total chunks generated")
    chunks: List[Chunk] = Field(description="List of chunks")
    statistics: Optional[ChunkStatistics] = Field(default=None, description="Statistics")


class FileChunkResult(BaseModel):
    """Chunking result wrapper for a file"""
    filename: str = Field(description="File name")
    path: str = Field(description="Absolute file path")
    relative_path: Optional[str] = Field(default=None, description="Relative path")
    result: ChunkResult = Field(description="Chunking result")


class ChunkError(BaseModel):
    """Error information for failed chunking"""
    file: str = Field(description="Failed file path")
    error: str = Field(description="Error message")


class ChunkSummary(BaseModel):
    """Summary statistics for chunking"""
    total_files_scanned: Optional[int] = Field(default=None, description="Total files scanned")
    total_chunks_generated: Optional[int] = Field(default=None, description="Total chunks generated")
    total_chars_processed: Optional[int] = Field(default=None, description="Total characters processed")
    avg_chunks_per_file: Optional[float] = Field(default=None, description="Average chunks per file")


class ChunkResponse(BaseModel):
    """Response from chunking service"""
    total_files: Optional[int] = Field(default=None, description="Total files")
    success_count: Optional[int] = Field(default=None, description="Successfully chunked files")
    failed_count: Optional[int] = Field(default=None, description="Failed files")
    results: List[FileChunkResult] = Field(default_factory=list, description="Chunking results per file")
    errors: Optional[List[ChunkError]] = Field(default=None, description="Error list")
    summary: Optional[ChunkSummary] = Field(default=None, description="Summary statistics")


# ============================================
# Embedding Service Schemas
# ============================================

class EmbeddingRequest(BaseModel):
    """Request for embedding service"""
    model: str = Field(description="Model name")
    input: List[str] = Field(description="Text inputs to embed")
    encoding_format: Optional[str] = Field(default="float", description="Encoding format")
    dimensions: Optional[int] = Field(default=None, description="Output dimensions")


class EmbeddingData(BaseModel):
    """Single embedding result"""
    index: int = Field(description="Input index")
    object: str = Field(default="embedding", description="Object type")
    embedding: List[float] = Field(description="Embedding vector")


class EmbeddingUsage(BaseModel):
    """Token usage for embedding"""
    prompt_tokens: int = Field(description="Prompt tokens used")
    total_tokens: int = Field(description="Total tokens used")
    completion_tokens: Optional[int] = Field(default=0, description="Completion tokens")
    prompt_tokens_details: Optional[Dict[str, Any]] = Field(default=None, description="Token details")


class EmbeddingResponse(BaseModel):
    """Response from embedding service"""
    id: Optional[str] = Field(default=None, description="Request ID")
    object: Optional[str] = Field(default="list", description="Object type")
    created: Optional[int] = Field(default=None, description="Creation timestamp")
    model: Optional[str] = Field(default=None, description="Model used")
    data: List[EmbeddingData] = Field(description="Embedding results")
    usage: Optional[EmbeddingUsage] = Field(default=None, description="Token usage")


# ============================================
# Rerank Service Schemas
# ============================================

class RerankRequest(BaseModel):
    """Request for rerank service"""
    query: str = Field(description="Query text")
    documents: List[str] = Field(description="Documents to rerank")
    model: Optional[str] = Field(default=None, description="Model name")
    top_n: Optional[int] = Field(default=None, description="Return top N results")
    return_documents: Optional[bool] = Field(default=True, description="Return document content")


class RerankDocument(BaseModel):
    """Document in rerank result"""
    text: str = Field(description="Document text")
    multi_modal: Optional[Any] = Field(default=None, description="Multi-modal data")


class RerankResult(BaseModel):
    """Single rerank result"""
    index: int = Field(description="Original document index")
    document: Optional[RerankDocument] = Field(default=None, description="Document")
    relevance_score: float = Field(description="Relevance score (0-1)")
    doc_name: Optional[str] = Field(default=None, description="Document name")


class RerankUsage(BaseModel):
    """Token usage for rerank"""
    prompt_tokens: Optional[int] = Field(default=None, description="Prompt tokens")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens")


class RerankResponse(BaseModel):
    """Response from rerank service"""
    id: Optional[str] = Field(default=None, description="Request ID")
    model: Optional[str] = Field(default=None, description="Model used")
    usage: Optional[RerankUsage] = Field(default=None, description="Token usage")
    results: List[RerankResult] = Field(description="Reranked results")


# ============================================
# Document Storage Service Schemas
# ============================================

class ChunkForInsert(BaseModel):
    """Chunk data for bulk insert"""
    chunk_id: str = Field(description="Chunk unique ID")
    content: str = Field(description="Chunk text content")
    vector: List[float] = Field(description="Embedding vector")


class BulkInsertRequest(BaseModel):
    """Request for bulk document insert (V2 with kb_id)"""
    kb_id: str = Field(description="Knowledge base ID for data isolation")
    doc_id: str = Field(description="Document unique ID (MD5)")
    doc_name: str = Field(description="Document name for display")
    chunks: List[ChunkForInsert] = Field(description="Chunks to insert")


class BulkInsertResponse(BaseModel):
    """Response from bulk insert"""
    success: bool = Field(description="Insert success status")
    message: Optional[str] = Field(default=None, description="Result message")


# ============================================
# Hybrid Search Service Schemas
# ============================================

class HybridSearchRequest(BaseModel):
    """Request for hybrid search (V2 with kb_id)"""
    kb_id: str = Field(description="Knowledge base ID (single or comma-separated multiple)")
    query_text: str = Field(description="Query text for ES search")
    query_vector: List[float] = Field(description="Query vector for Milvus search")
    top_k: Optional[int] = Field(default=15, description="Top-k results per search type")


class SearchResult(BaseModel):
    """Single search result (V2 with kb_id)"""
    chunk_id: str = Field(description="Chunk unique ID")
    doc_id: str = Field(description="Document ID")
    kb_id: str = Field(description="Knowledge base ID")
    doc_name: str = Field(description="Document name")
    content: str = Field(description="Chunk content")
    score: float = Field(description="Search score")
    score_type: str = Field(description="Score type: es_score or milvus_score")


class HybridSearchResponse(BaseModel):
    """Response from hybrid search"""
    results: List[SearchResult] = Field(description="Search results")


# ============================================
# LLM Service Schemas
# ============================================

class ChatMessage(BaseModel):
    """Chat message for LLM"""
    role: str = Field(description="Role: system/user/assistant")
    content: str = Field(description="Message content")


class ChatRequest(BaseModel):
    """Request for LLM chat completion"""
    model: str = Field(description="Model name")
    messages: List[ChatMessage] = Field(description="Chat messages")
    temperature: Optional[float] = Field(default=0.3, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=2000, description="Max tokens to generate")
    top_p: Optional[float] = Field(default=1.0, description="Top-p sampling")


class ChatChoice(BaseModel):
    """Chat completion choice"""
    index: int = Field(description="Choice index")
    message: ChatMessage = Field(description="Generated message")
    finish_reason: Optional[str] = Field(default=None, description="Finish reason")


class ChatUsage(BaseModel):
    """Token usage for chat completion"""
    prompt_tokens: int = Field(description="Prompt tokens")
    completion_tokens: int = Field(description="Completion tokens")
    total_tokens: int = Field(description="Total tokens")


class ChatResponse(BaseModel):
    """Response from LLM chat completion"""
    id: Optional[str] = Field(default=None, description="Request ID")
    object: Optional[str] = Field(default="chat.completion", description="Object type")
    created: Optional[int] = Field(default=None, description="Creation timestamp")
    model: Optional[str] = Field(default=None, description="Model used")
    choices: List[ChatChoice] = Field(description="Chat choices")
    usage: Optional[ChatUsage] = Field(default=None, description="Token usage")


# ============================================
# Pipeline Internal Schemas
# ============================================

class ChunkWithVector(BaseModel):
    """Chunk with embedding vector (internal use)"""
    chunk_id: str = Field(description="Chunk unique ID")
    content: str = Field(description="Chunk text content")
    vector: List[float] = Field(description="Embedding vector")
    global_index: int = Field(description="Global index in flattened list")
    local_index: int = Field(description="Local index in document")


class RerankResultWithSource(BaseModel):
    """Rerank result with source information for context assembly"""
    index: int = Field(description="Original document index")
    document: Optional[RerankDocument] = Field(default=None, description="Document")
    relevance_score: float = Field(description="Relevance score (0-1)")
    kb_id: Optional[str] = Field(default=None, description="Knowledge base ID")
    doc_name: Optional[str] = Field(default=None, description="Document name")


class DocumentForInsert(BaseModel):
    """Document ready for insertion (internal use)"""
    doc_id: str = Field(description="Document unique ID")
    doc_name: str = Field(description="Document name")
    chunks: List[ChunkWithVector] = Field(description="Chunks with vectors")


class IngestionResult(BaseModel):
    """Result of ingestion pipeline"""
    total_files: int = Field(description="Total files processed")
    success_files: int = Field(description="Successfully inserted files")
    failed_files: int = Field(description="Failed files")
    total_chunks: int = Field(description="Total chunks inserted")
    kb_id: Optional[str] = Field(default=None, description="Knowledge base ID")
    errors: List[str] = Field(default_factory=list, description="Error messages")


class QueryResult(BaseModel):
    """Result of query pipeline"""
    query: str = Field(description="Original query")
    answer: str = Field(description="Generated answer")
    context_chunks: int = Field(description="Number of context chunks used")
    kb_ids: Optional[str] = Field(default=None, description="Knowledge base IDs queried")
    reranked_results: Optional[List[RerankResultWithSource]] = Field(default=None, description="Reranked results with sources")
    usage: Optional[Dict[str, Any]] = Field(default=None, description="Token usage info")