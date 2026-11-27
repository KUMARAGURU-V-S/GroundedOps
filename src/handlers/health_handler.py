"""
AWS Lambda Health & Diagnostics Handler for GroundedOps.
Provides /health and /stats endpoints for API Gateway monitoring and diagnostics.
"""

from typing import Any, Dict

from ..core.rag_pipeline import RAGPipeline
from ..utils.logger import get_logger
from ..utils.response import error_response, success_response

logger = get_logger("groundedops.health_handler")

pipeline = RAGPipeline()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Return health check and pipeline status."""
    try:
        stats = pipeline.get_pipeline_stats()
        return success_response(data=stats, status_code=200)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return error_response(
            message=f"Health check failed: {str(e)}",
            status_code=500,
            error_code="UNHEALTHY",
        )
