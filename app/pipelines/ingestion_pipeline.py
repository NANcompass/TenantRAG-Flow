"""
Ingestion Pipeline V2
Handles document chunking, embedding generation, and bulk insertion with kb_id support

Flow:
1. Document Chunking Service -> Extract all chunk contents -> flatten
2. Embedding Service -> Generate vectors for batch contents (max 100 per batch)
3. Data alignment -> Fill vectors back to corresponding chunks
4. Bulk Insert Service -> Store documents with vectors in MySQL/ES/Milvus (max 100 chunks per request)
"""
import hashlib
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from app.utils.http_client import http_client, HTTPClientError
from app.utils.logger import get_logger
from app.schemas.models import (
    ChunkRequest,
    ChunkResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    BulkInsertRequest,
    BulkInsertResponse,
    ChunkWithVector,
    ChunkForInsert,
    IngestionResult,
)

logger = get_logger(__name__)


class IngestionPipeline:
    """
    Ingestion Pipeline V2 for RAG System

    Handles the complete flow of document ingestion with multi-tenant support:
    1. Chunking documents
    2. Generating embeddings (batch processing, max 100 per batch)
    3. Storing in database (batch insertion, max 100 chunks per request)
    """

    def __init__(self):
        """Initialize pipeline with configuration from .env"""
        # Chunking config
        self.chunk_service_url = settings.CHUNK_SERVICE_URL
        self.chunk_service_timeout = settings.CHUNK_SERVICE_TIMEOUT

        # Embedding config
        self.embedding_service_url = settings.EMBEDDING_SERVICE_URL
        self.embedding_service_timeout = settings.EMBEDDING_SERVICE_TIMEOUT
        self.embedding_model = settings.EMBEDDING_MODEL

        # Document storage config
        self.document_service_url = settings.DOCUMENT_SERVICE_URL
        self.document_service_timeout = settings.DOCUMENT_SERVICE_TIMEOUT

        # Chunking parameters
        self.default_chunk_size = settings.DEFAULT_CHUNK_SIZE
        self.default_chunk_overlap = settings.DEFAULT_CHUNK_OVERLAP
        self.default_chunk_mode = settings.DEFAULT_CHUNK_MODE
        self.semantic_split = settings.SEMANTIC_SPLIT
        self.preserve_hierarchy = settings.PRESERVE_HIERARCHY

        # V2: Batch size limits
        self.bulk_insert_batch_size = settings.BULK_INSERT_BATCH_SIZE  # max 100 chunks per request

        logger.info("IngestionPipeline V2 initialized with kb_id support and batch limits")

    def _generate_doc_id(self, filename: str) -> str:
        """
        Generate document ID using MD5 hash of filename

        Args:
            filename: File name

        Returns:
            MD5 hash string as doc_id
        """
        return hashlib.md5(filename.encode()).hexdigest()

    def _generate_chunk_id(self, doc_id: str, local_index: int) -> str:
        """
        Generate chunk ID in format: {doc_id}_para_{index}

        Args:
            doc_id: Document ID
            local_index: Local index in document

        Returns:
            Chunk ID string
        """
        return f"{doc_id}_para_{local_index}"

    async def _call_chunk_service(self, request: ChunkRequest) -> ChunkResponse:
        """
        Call document chunking service

        Args:
            request: Chunking request

        Returns:
            Chunking response

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.chunk_service_url}/chunk/file"
        logger.info(f"Calling chunk service: {url}")

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.chunk_service_timeout,
            service_name="ChunkService"
        )

        return ChunkResponse(**response_data)

    async def _call_embedding_service(self, texts: List[str]) -> List[List[float]]:
        """
        Call embedding service for batch texts

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (same order as input)

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.embedding_service_url}/v1/embeddings"
        logger.info(f"Calling embedding service: {url} for {len(texts)} texts")

        # Prepare request
        request = EmbeddingRequest(
            model=self.embedding_model,
            input=texts
        )

        headers = {}
        if settings.EMBEDDING_API_KEY:
            headers["Authorization"] = f"Bearer {settings.EMBEDDING_API_KEY}"

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.embedding_service_timeout,
            headers=headers if headers else None,
            service_name="EmbeddingService"
        )

        response = EmbeddingResponse(**response_data)

        # Sort by index to ensure correct order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        embeddings = [item.embedding for item in sorted_data]

        logger.info(f"Received {len(embeddings)} embeddings")
        return embeddings

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings in batches to respect service limits

        V2: Process embeddings in batches of max 100 texts per call

        Args:
            texts: List of all text strings to embed

        Returns:
            List of all embedding vectors (same order as input)

        Raises:
            HTTPClientError: When service call fails
        """
        all_embeddings = []
        batch_size = self.bulk_insert_batch_size  # Use same limit as bulk insert (100)
        batch_count = (len(texts) + batch_size - 1) // batch_size

        logger.info(f"Generating embeddings for {len(texts)} texts in {batch_count} batches")

        for batch_idx in range(batch_count):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]

            logger.info(f"Processing embedding batch {batch_idx + 1}/{batch_count}: {len(batch_texts)} texts")

            batch_embeddings = await self._call_embedding_service(batch_texts)
            all_embeddings.extend(batch_embeddings)

        logger.info(f"All embeddings generated: {len(all_embeddings)} total vectors")
        return all_embeddings

    async def _call_bulk_insert(self, request: BulkInsertRequest) -> BulkInsertResponse:
        """
        Call bulk insert service

        Args:
            request: Bulk insert request

        Returns:
            Bulk insert response

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.document_service_url}/api/documents/bulk"
        logger.info(f"Calling bulk insert service: {url} for doc_id={request.doc_id}")

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.document_service_timeout,
            service_name="DocumentService"
        )

        return BulkInsertResponse(**response_data)

    def _extract_and_flatten_chunks(
        self,
        chunk_response: ChunkResponse
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extract chunks from chunking response and flatten for embedding

        Key challenge: Chunking service returns tree structure (file -> chunks),
        but embedding service needs flat array. We need to track the mapping
        to fill vectors back correctly.

        Args:
            chunk_response: Response from chunking service

        Returns:
            Tuple of (chunk_info_list, flattened_contents)
            - chunk_info_list: List of dicts with chunk metadata and mapping info
            - flattened_contents: List of content strings for embedding
        """
        chunk_info_list = []
        flattened_contents = []
        global_index = 0

        for file_result in chunk_response.results:
            filename = file_result.filename
            doc_id = self._generate_doc_id(filename)
            chunks = file_result.result.chunks

            logger.info(
                f"Processing file: {filename}, doc_id={doc_id}, "
                f"chunks={len(chunks)}"
            )

            for local_index, chunk in enumerate(chunks):
                # Store mapping info
                chunk_info = {
                    "doc_id": doc_id,
                    "doc_name": filename,
                    "chunk_id": self._generate_chunk_id(doc_id, local_index),
                    "content": chunk.content,
                    "global_index": global_index,
                    "local_index": local_index,
                }
                chunk_info_list.append(chunk_info)

                # Add content to flattened list
                flattened_contents.append(chunk.content)
                global_index += 1

        logger.info(
            f"Flattened {len(chunk_response.results)} files, "
            f"{len(flattened_contents)} total chunks"
        )

        return chunk_info_list, flattened_contents

    def _fill_vectors_to_chunks(
        self,
        chunk_info_list: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> Dict[str, List[ChunkWithVector]]:
        """
        Fill embedding vectors back to corresponding chunks

        Critical: Ensure index alignment - embedding[i] must match chunk[i]

        Args:
            chunk_info_list: List of chunk info from flattening
            embeddings: List of embedding vectors from embedding service

        Returns:
            Dict mapping doc_id -> list of chunks with vectors
        """
        if len(chunk_info_list) != len(embeddings):
            raise ValueError(
                f"Index mismatch! Chunks: {len(chunk_info_list)}, "
                f"Embeddings: {len(embeddings)}"
            )

        # Group chunks by doc_id
        documents_dict: Dict[str, List[ChunkWithVector]] = {}

        for chunk_info, embedding in zip(chunk_info_list, embeddings):
            doc_id = chunk_info["doc_id"]

            chunk_with_vector = ChunkWithVector(
                chunk_id=chunk_info["chunk_id"],
                content=chunk_info["content"],
                vector=embedding,
                global_index=chunk_info["global_index"],
                local_index=chunk_info["local_index"],
            )

            if doc_id not in documents_dict:
                documents_dict[doc_id] = []
            documents_dict[doc_id].append(chunk_with_vector)

        logger.info(f"Filled vectors for {len(documents_dict)} documents")
        return documents_dict

    async def run(
        self,
        path: str,
        kb_id: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        mode: Optional[str] = None,
        semantic_split: Optional[bool] = None,
        preserve_hierarchy: Optional[bool] = None
    ) -> IngestionResult:
        """
        Run the complete ingestion pipeline V2 with kb_id support

        Args:
            path: File or folder path to ingest
            kb_id: Knowledge base ID for data isolation (required)
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            mode: Override default chunking mode
            semantic_split: Override semantic split setting
            preserve_hierarchy: Override preserve hierarchy setting

        Returns:
            IngestionResult with statistics
        """
        logger.info(f"Starting ingestion pipeline V2 for path: {path}, kb_id: {kb_id}")

        result = IngestionResult(
            total_files=0,
            success_files=0,
            failed_files=0,
            total_chunks=0,
            kb_id=kb_id,
            errors=[]
        )

        try:
            # Step 1: Call chunking service
            logger.info("Step 1: Calling chunking service...")
            chunk_request = ChunkRequest(
                path=path,
                mode=mode or self.default_chunk_mode,
                chunk_size=chunk_size or self.default_chunk_size,
                chunk_overlap=chunk_overlap or self.default_chunk_overlap,
                semantic_split=semantic_split if semantic_split is not None else self.semantic_split,
                preserve_hierarchy=preserve_hierarchy if preserve_hierarchy is not None else self.preserve_hierarchy
            )

            chunk_response = await self._call_chunk_service(chunk_request)
            result.total_files = len(chunk_response.results)

            # Check for chunking errors
            if chunk_response.errors:
                for error in chunk_response.errors:
                    error_msg = f"Chunking error - {error.file}: {error.error}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

            logger.info(
                f"Chunking completed: {chunk_response.success_count} success, "
                f"{chunk_response.failed_count} failed"
            )

            if not chunk_response.results:
                logger.warning("No files were successfully chunked")
                result.failed_files = chunk_response.failed_count or 0
                return result

            # Step 2: Extract and flatten chunks
            logger.info("Step 2: Extracting and flattening chunks...")
            chunk_info_list, flattened_contents = self._extract_and_flatten_chunks(chunk_response)

            if not flattened_contents:
                logger.warning("No content to embed")
                return result

            # Step 3: Generate embeddings in batches (max 100 per batch)
            logger.info(f"Step 3: Generating embeddings in batches (max {self.bulk_insert_batch_size} per batch)...")
            embeddings = await self._generate_embeddings_batch(flattened_contents)

            # Step 4: Fill vectors back to chunks
            logger.info("Step 4: Filling vectors back to chunks...")
            documents_dict = self._fill_vectors_to_chunks(chunk_info_list, embeddings)

            # Step 5: Bulk insert with batching (max 100 chunks per request)
            logger.info(f"Step 5: Bulk inserting documents with kb_id={kb_id} (max {self.bulk_insert_batch_size} chunks per request)...")

            # We need to track doc_name separately
            doc_name_map = {}
            for chunk_info in chunk_info_list:
                if chunk_info["doc_id"] not in doc_name_map:
                    doc_name_map[chunk_info["doc_id"]] = chunk_info["doc_name"]

            # Process each document with batch insertion
            success_count = 0
            failed_count = 0

            for doc_id, chunks in documents_dict.items():
                doc_name = doc_name_map.get(doc_id, doc_id)

                try:
                    # Split chunks into batches of max 100
                    batch_count = (len(chunks) + self.bulk_insert_batch_size - 1) // self.bulk_insert_batch_size
                    logger.info(f"Document {doc_id} ({doc_name}): {len(chunks)} chunks -> {batch_count} batches")

                    # Insert each batch sequentially for the same document
                    # (Upsert will handle duplicate removal automatically)
                    batch_success = True
                    for batch_idx in range(batch_count):
                        start_idx = batch_idx * self.bulk_insert_batch_size
                        end_idx = min(start_idx + self.bulk_insert_batch_size, len(chunks))
                        batch_chunks = chunks[start_idx:end_idx]

                        logger.info(f"Inserting batch {batch_idx + 1}/{batch_count} for {doc_id}: {len(batch_chunks)} chunks")

                        insert_request = BulkInsertRequest(
                            kb_id=kb_id,
                            doc_id=doc_id,
                            doc_name=doc_name,
                            chunks=[
                                ChunkForInsert(
                                    chunk_id=c.chunk_id,
                                    content=c.content,
                                    vector=c.vector
                                ) for c in batch_chunks
                            ]
                        )

                        insert_response = await self._call_bulk_insert(insert_request)

                        if not insert_response.success:
                            error_msg = f"Bulk insert failed for {doc_id} batch {batch_idx + 1}: {insert_response.message}"
                            logger.error(error_msg)
                            result.errors.append(error_msg)
                            batch_success = False
                            break

                    if batch_success:
                        success_count += 1
                        result.total_chunks += len(chunks)
                        logger.info(f"Document {doc_id} inserted successfully across {batch_count} batches")
                    else:
                        failed_count += 1

                except HTTPClientError as e:
                    error_msg = f"HTTP error inserting {doc_id}: {e.message}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    failed_count += 1
                except Exception as e:
                    error_msg = f"Unexpected error inserting {doc_id}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    failed_count += 1

            result.success_files = success_count
            result.failed_files = failed_count

            logger.info(
                f"Ingestion V2 completed: {success_count} documents inserted, "
                f"{failed_count} failed, {result.total_chunks} total chunks, kb_id={kb_id}"
            )

        except HTTPClientError as e:
            error_msg = f"Pipeline failed due to HTTP error: {e.message}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        except Exception as e:
            error_msg = f"Pipeline failed with unexpected error: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return result


# Global pipeline instance
ingestion_pipeline = IngestionPipeline()