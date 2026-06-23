"""Pipelines module"""
from .ingestion_pipeline import IngestionPipeline, ingestion_pipeline
from .query_pipeline import QueryPipeline, query_pipeline

__all__ = [
    "IngestionPipeline",
    "ingestion_pipeline",
    "QueryPipeline",
    "query_pipeline",
]
