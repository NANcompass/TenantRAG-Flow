"""
RAG System Configuration Module
All configurations are loaded from .env file
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file"""

    # ============================================
    # Application Settings
    # ============================================
    APP_NAME: str = Field(description="Application name")
    APP_VERSION: str = Field(description="Application version")
    DEBUG: bool = Field(default=True, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    LOG_FORMAT: str = Field(description="Log format string")

    # ============================================
    # Service URLs
    # ============================================
    CHUNK_SERVICE_URL: str = Field(description="Document chunking service URL")
    CHUNK_SERVICE_TIMEOUT: int = Field(default=300, description="Chunk service timeout in seconds")

    EMBEDDING_SERVICE_URL: str = Field(description="Embedding service URL")
    EMBEDDING_SERVICE_TIMEOUT: int = Field(default=120, description="Embedding service timeout in seconds")

    RERANK_SERVICE_URL: str = Field(description="Rerank service URL")
    RERANK_SERVICE_TIMEOUT: int = Field(default=60, description="Rerank service timeout in seconds")

    LLM_SERVICE_URL: str = Field(description="LLM service URL")
    LLM_SERVICE_TIMEOUT: int = Field(default=120, description="LLM service timeout in seconds")

    DOCUMENT_SERVICE_URL: str = Field(description="Document storage service URL")
    DOCUMENT_SERVICE_TIMEOUT: int = Field(default=60, description="Document service timeout in seconds")

    # ============================================
    # Model Configuration
    # ============================================
    EMBEDDING_MODEL: str = Field(description="Embedding model name")
    RERANK_MODEL: str = Field(description="Rerank model name")
    LLM_MODEL: str = Field(description="LLM model name")

    # ============================================
    # Ingestion Pipeline Configuration
    # ============================================
    DEFAULT_CHUNK_SIZE: int = Field(default=500, description="Default chunk size in characters")
    DEFAULT_CHUNK_OVERLAP: int = Field(default=50, description="Default chunk overlap in characters")
    DEFAULT_CHUNK_MODE: str = Field(default="general", description="Default chunking mode")
    SEMANTIC_SPLIT: bool = Field(default=False, description="Enable semantic splitting")
    PRESERVE_HIERARCHY: bool = Field(default=False, description="Preserve heading hierarchy")

    PARENT_CHUNK_SIZE: int = Field(default=1500, description="Parent chunk size for parent-child mode")
    CHILD_CHUNK_SIZE: int = Field(default=200, description="Child chunk size for parent-child mode")
    CHILD_CHUNK_OVERLAP: int = Field(default=20, description="Child chunk overlap for parent-child mode")

    # V2: Bulk insert batch size limit
    BULK_INSERT_BATCH_SIZE: int = Field(default=100, description="Maximum chunks per bulk insert request")

    # ============================================
    # Query Pipeline Configuration
    # ============================================
    DEFAULT_TOP_K: int = Field(default=15, description="Default top-k for hybrid search")
    RERANK_TOP_N: int = Field(default=5, description="Top-n results from rerank")
    RERANK_THRESHOLD: float = Field(default=0.4, description="Rerank relevance score threshold")
    RERANK_RETURN_DOCUMENTS: bool = Field(default=True, description="Return documents in rerank response")

    LLM_TEMPERATURE: float = Field(default=0.3, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=2000, description="LLM max tokens")

    # ============================================
    # Retry Configuration
    # ============================================
    MAX_RETRIES: int = Field(default=3, description="Maximum retry attempts")
    RETRY_DELAY: float = Field(default=1.0, description="Initial retry delay in seconds")
    RETRY_BACKOFF_FACTOR: float = Field(default=2.0, description="Retry backoff multiplier")

    # ============================================
    # API Keys (Optional)
    # ============================================
    EMBEDDING_API_KEY: Optional[str] = Field(default=None, description="Embedding service API key")
    RERANK_API_KEY: Optional[str] = Field(default=None, description="Rerank service API key")
    LLM_API_KEY: Optional[str] = Field(default=None, description="LLM service API key")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
