"""
RAG System Main Application
FastAPI application entry point
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.utils.logger import setup_logging, get_logger
from app.utils.http_client import HTTPClientError
from app.api import ingestion_router, query_router

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
RAG System - Retrieval Augmented Generation Pipeline

## Features

### Ingestion Pipeline
- Document chunking with semantic splitting
- Batch embedding generation
- Multi-database storage (MySQL, Elasticsearch, Milvus)

### Query Pipeline
- Hybrid search (ES + Milvus)
- Reranking for relevance
- LLM-powered answer generation

All configurations are loaded from .env file.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPClientError)
async def http_client_error_handler(request: Request, exc: HTTPClientError):
    """Handle HTTP client errors"""
    logger.error(f"HTTP Client Error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={
            "error": exc.message,
            "status_code": exc.status_code,
            "details": exc.response_body
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(ingestion_router)
app.include_router(query_router)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "ingestion": {
                "sync": "POST /ingest/file",
                "async": "POST /ingest/async",
                "json": "POST /ingest/file/json"
            },
            "query": {
                "params": "POST /query/search?query=...",
                "json": "POST /query/search/json"
            }
        }
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info("Configuration loaded from .env file")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info(f"Shutting down {settings.APP_NAME}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
