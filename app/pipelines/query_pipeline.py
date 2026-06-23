"""
Query Pipeline V2
Handles query processing, hybrid search, reranking, and LLM generation with kb_id support

Flow:
1. Embedding Service -> Convert query to vector
2. Hybrid Search Service -> ES + Milvus search with kb_id filtering, dedupe results
3. Rerank Service -> Re-order results by relevance (standardize scores)
4. Context Assembly -> Build context with source annotations [kb_id / doc_name]
5. LLM Service -> Generate answer based on filtered context with source attribution
"""
from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.utils.http_client import http_client, HTTPClientError
from app.utils.logger import get_logger
from app.schemas.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    RerankRequest,
    RerankResponse,
    RerankResultWithSource,
    ChatRequest,
    ChatResponse,
    QueryResult,
    SearchResult,
)

logger = get_logger(__name__)


class QueryPipeline:
    """
    Query Pipeline V2 for RAG System

    Handles the complete flow of query processing with multi-tenant support:
    1. Query embedding
    2. Hybrid search (ES + Milvus) with kb_id filtering
    3. Reranking (standardize ES and Milvus scores)
    4. Context assembly with source annotations
    5. LLM generation with source attribution
    """

    def __init__(self):
        """Initialize pipeline with configuration from .env"""
        # Embedding config
        self.embedding_service_url = settings.EMBEDDING_SERVICE_URL
        self.embedding_service_timeout = settings.EMBEDDING_SERVICE_TIMEOUT
        self.embedding_model = settings.EMBEDDING_MODEL

        # Document service (hybrid search)
        self.document_service_url = settings.DOCUMENT_SERVICE_URL
        self.document_service_timeout = settings.DOCUMENT_SERVICE_TIMEOUT

        # Rerank config
        self.rerank_service_url = settings.RERANK_SERVICE_URL
        self.rerank_service_timeout = settings.RERANK_SERVICE_TIMEOUT
        self.rerank_model = settings.RERANK_MODEL
        self.rerank_top_n = settings.RERANK_TOP_N
        self.rerank_threshold = settings.RERANK_THRESHOLD
        self.rerank_return_documents = settings.RERANK_RETURN_DOCUMENTS

        # LLM config
        self.llm_service_url = settings.LLM_SERVICE_URL
        self.llm_service_timeout = settings.LLM_SERVICE_TIMEOUT
        self.llm_model = settings.LLM_MODEL
        self.llm_temperature = settings.LLM_TEMPERATURE
        self.llm_max_tokens = settings.LLM_MAX_TOKENS

        # Search config
        self.default_top_k = settings.DEFAULT_TOP_K

        logger.info("QueryPipeline V2 initialized with kb_id support and source attribution")

    async def _get_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for query text

        Args:
            query: Query text string

        Returns:
            Embedding vector

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.embedding_service_url}/v1/embeddings"
        logger.info(f"Getting embedding for query: {query[:50]}...")

        request = EmbeddingRequest(
            model=self.embedding_model,
            input=[query]
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

        if not response.data:
            raise ValueError("Empty embedding response")

        return response.data[0].embedding

    async def _hybrid_search(
        self,
        kb_id: str,
        query_text: str,
        query_vector: List[float],
        top_k: Optional[int] = None
    ) -> HybridSearchResponse:
        """
        Perform hybrid search (ES + Milvus) with kb_id filtering

        V2: Supports single or multiple kb_id (comma-separated)

        Args:
            kb_id: Knowledge base ID (single or comma-separated multiple)
            query_text: Query text for ES search
            query_vector: Query vector for Milvus search
            top_k: Number of results per search type

        Returns:
            Hybrid search response with deduplicated results

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.document_service_url}/api/search/hybrid"
        logger.info(f"Performing hybrid search: kb_id={kb_id}, top_k={top_k or self.default_top_k}")

        request = HybridSearchRequest(
            kb_id=kb_id,
            query_text=query_text,
            query_vector=query_vector,
            top_k=top_k or self.default_top_k
        )

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.document_service_timeout,
            service_name="HybridSearchService"
        )

        response = HybridSearchResponse(**response_data)
        logger.info(f"Hybrid search returned {len(response.results)} results for kb_id={kb_id}")

        return response

    async def _rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> RerankResponse:
        """
        Rerank documents by relevance to query

        Args:
            query: Query text
            documents: List of document texts
            top_n: Number of top results to return

        Returns:
            Rerank response with relevance scores

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.rerank_service_url}/v1/rerank"
        logger.info(f"Reranking {len(documents)} documents")

        request = RerankRequest(
            query=query,
            documents=documents,
            model=self.rerank_model,
            top_n=top_n or self.rerank_top_n,
            return_documents=self.rerank_return_documents
        )

        headers = {}
        if settings.RERANK_API_KEY:
            headers["Authorization"] = f"Bearer {settings.RERANK_API_KEY}"

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.rerank_service_timeout,
            headers=headers if headers else None,
            service_name="RerankService"
        )

        response = RerankResponse(**response_data)
        logger.info(f"Rerank returned {len(response.results)} results")

        return response

    def _enrich_rerank_results_with_sources(
        self,
        rerank_results: List[Any],
        search_results: List[SearchResult]
    ) -> List[RerankResultWithSource]:
        """
        Enrich rerank results with kb_id and doc_name from search results

        V2: Track source information for context annotation

        Args:
            rerank_results: Reranked results from rerank service
            search_results: Original search results with kb_id and doc_name

        Returns:
            Rerank results with source information
        """
        enriched_results = []

        for rerank_result in rerank_results:
            index = rerank_result.index
            if 0 <= index < len(search_results):
                search_result = search_results[index]
                enriched = RerankResultWithSource(
                    index=rerank_result.index,
                    document=rerank_result.document,
                    relevance_score=rerank_result.relevance_score,
                    kb_id=search_result.kb_id,
                    doc_name=search_result.doc_name
                )
                enriched_results.append(enriched)
            else:
                logger.warning(f"Rerank result index {index} out of range")

        return enriched_results

    async def _generate_answer(
        self,
        query: str,
        context: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> ChatResponse:
        """
        Generate answer using LLM

        Args:
            query: User query
            context: Context assembled from search results
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Chat completion response

        Raises:
            HTTPClientError: When service call fails
        """
        url = f"{self.llm_service_url}/v1/chat/completions"
        logger.info("Generating answer with LLM")

        # Build prompt with context
        prompt = f"""你是一个专业的知识库助手。请严格基于以下参考资料回答用户的问题。如果资料中未提及相关内容，请直接回答"知识库中未查到相关信息"，切勿胡编乱造。

【参考资料】：
{context}

【用户问题】：
{query}"""

        request = ChatRequest(
            model=self.llm_model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature or self.llm_temperature,
            max_tokens=max_tokens or self.llm_max_tokens
        )

        headers = {}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

        response_data = await http_client.post(
            url=url,
            json_data=request.model_dump(exclude_none=True),
            timeout=self.llm_service_timeout,
            headers=headers if headers else None,
            service_name="LLMService"
        )

        response = ChatResponse(**response_data)
        logger.info("LLM response generated successfully")

        return response

    def _extract_contents_from_search(
        self,
        search_results: List[SearchResult]
    ) -> List[str]:
        """
        Extract content strings from search results for reranking

        Args:
            search_results: List of search results

        Returns:
            List of content strings
        """
        return [result.content for result in search_results]

    def _filter_and_assemble_context(
        self,
        rerank_results: List[RerankResultWithSource],
        threshold: Optional[float] = None
    ) -> str:
        """
        Filter reranked results by threshold and assemble context with source annotations

        V2: Add source attribution [来源: kb_id / 文档: doc_name]

        Args:
            rerank_results: Reranked results with relevance scores and source info
            threshold: Minimum relevance score (default from config)

        Returns:
            Assembled context string with source annotations
        """
        threshold = threshold or self.rerank_threshold

        context_parts = []
        for result in rerank_results:
            if result.relevance_score >= threshold:
                if result.document and result.document.text:
                    # Build source annotation
                    source_annotation = f"[来源: {result.kb_id} / 文档: {result.doc_name}]"

                    # Add content with source annotation
                    annotated_content = f"{source_annotation}\n{result.document.text}"
                    context_parts.append(annotated_content)

                    logger.debug(
                        f"Included chunk with score {result.relevance_score:.4f} "
                        f"from {result.kb_id}/{result.doc_name}"
                    )
                else:
                    logger.warning(f"Rerank result missing document text at index {result.index}")

        context = "\n\n".join(context_parts)
        logger.info(
            f"Assembled context from {len(context_parts)}/{len(rerank_results)} "
            f"chunks (threshold={threshold}) with source annotations"
        )

        return context

    async def run(
        self,
        query: str,
        kb_id: str,
        top_k: Optional[int] = None,
        rerank_top_n: Optional[int] = None,
        rerank_threshold: Optional[float] = None,
        temperature: Optional[float] = None
    ) -> QueryResult:
        """
        Run the complete query pipeline V2 with kb_id support

        Args:
            query: User query text
            kb_id: Knowledge base ID (single or comma-separated multiple)
            top_k: Override default top_k for search
            rerank_top_n: Override default rerank top_n
            rerank_threshold: Override default rerank threshold
            temperature: Override default LLM temperature

        Returns:
            QueryResult with answer, source attribution, and metadata
        """
        logger.info(f"Starting query pipeline V2 for: {query[:50]}..., kb_id={kb_id}")

        result = QueryResult(
            query=query,
            answer="",
            context_chunks=0,
            kb_ids=kb_id
        )

        try:
            # Step 1: Get query embedding
            logger.info("Step 1: Generating query embedding...")
            query_vector = await self._get_query_embedding(query)
            logger.info(f"Query embedding generated, dimension={len(query_vector)}")

            # Step 2: Hybrid search with kb_id
            logger.info(f"Step 2: Performing hybrid search for kb_id={kb_id}...")
            search_response = await self._hybrid_search(
                kb_id=kb_id,
                query_text=query,
                query_vector=query_vector,
                top_k=top_k
            )

            if not search_response.results:
                logger.warning(f"No results from hybrid search for kb_id={kb_id}")
                result.answer = "知识库中未查到相关信息。"
                return result

            # Step 3: Extract contents for reranking
            logger.info("Step 3: Extracting content for reranking...")
            documents = self._extract_contents_from_search(search_response.results)
            logger.info(f"Extracted {len(documents)} documents for reranking")

            # Step 4: Rerank (standardize ES and Milvus scores)
            logger.info("Step 4: Reranking documents to standardize scores...")
            rerank_response = await self._rerank(
                query=query,
                documents=documents,
                top_n=rerank_top_n
            )

            # Enrich rerank results with source information
            enriched_results = self._enrich_rerank_results_with_sources(
                rerank_response.results,
                search_response.results
            )

            result.reranked_results = enriched_results

            # Step 5: Filter and assemble context with source annotations
            logger.info("Step 5: Filtering and assembling context with source annotations...")
            context = self._filter_and_assemble_context(
                enriched_results,
                threshold=rerank_threshold
            )

            if not context:
                logger.warning("No context after filtering")
                result.answer = "知识库中未查到相关信息。"
                return result

            result.context_chunks = len([r for r in enriched_results
                                        if r.relevance_score >= (rerank_threshold or self.rerank_threshold)])

            # Step 6: Generate answer with LLM
            logger.info("Step 6: Generating answer with LLM...")
            chat_response = await self._generate_answer(
                query=query,
                context=context,
                temperature=temperature
            )

            if chat_response.choices:
                result.answer = chat_response.choices[0].message.content
                result.usage = chat_response.usage.model_dump() if chat_response.usage else None

            logger.info(f"Query pipeline V2 completed successfully for kb_id={kb_id}")

        except HTTPClientError as e:
            error_msg = f"Pipeline failed due to HTTP error: {e.message}"
            logger.error(error_msg)
            result.answer = f"抱歉，处理您的请求时发生错误: {e.message}"
        except Exception as e:
            error_msg = f"Pipeline failed with unexpected error: {str(e)}"
            logger.error(error_msg)
            result.answer = f"抱歉，处理您的请求时发生错误: {str(e)}"

        return result


# Global pipeline instance
query_pipeline = QueryPipeline()