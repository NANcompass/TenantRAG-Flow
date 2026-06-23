"""
RAG System - Entry Point

Run this to start the FastAPI server
"""
import uvicorn
from app.core.config import settings
from app.utils.logger import setup_logging

# Setup logging
setup_logging()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8021,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )