"""AWS Lambda Handlers."""
from .ingest_handler import lambda_handler as ingest_handler
from .query_handler import lambda_handler as query_handler
from .health_handler import lambda_handler as health_handler

__all__ = ["ingest_handler", "query_handler", "health_handler"]
