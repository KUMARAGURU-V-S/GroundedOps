"""
AWS Lambda Query Handler for GroundedOps.
Handles evidence-grounded queries via Amazon API Gateway POST /query.
Secured with Amazon Cognito User Pool Authorizer.
Retrieves context from S3 Vectors and invokes Amazon Bedrock Amazon Nova.
"""

import json
from typing import Any, Dict

from ..core.rag_pipeline import RAGPipeline
from ..utils.auth_validator import extract_auth_context
from ..utils.logger import get_logger
from ..utils.response import error_response, success_response

logger = get_logger("groundedops.query_handler")

# Initialize pipeline as reusable singleton across warm Lambda invocations
pipeline = RAGPipeline()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda entry point for grounded retrieval queries.
    """
    # 1. Extract and validate Cognito authentication context
    auth_ctx = extract_auth_context(event)
    logger.info(
        f"Query initiated by user '{auth_ctx.username}' ({auth_ctx.email})",
        extra={"extra_fields": {"user": auth_ctx.username, "groups": auth_ctx.groups}},
    )

    # 2. Parse request body
    body_raw = event.get("body")
    if not body_raw:
        return error_response(
            message="Request body cannot be empty.",
            status_code=400,
            error_code="MISSING_BODY",
        )

    try:
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    except json.JSONDecodeError:
        return error_response(
            message="Invalid JSON payload in request body.",
            status_code=400,
            error_code="INVALID_JSON",
        )

    question = body.get("question") or body.get("query")
    if not question or not str(question).strip():
        return error_response(
            message="Field 'question' is required and must not be empty.",
            status_code=400,
            error_code="VALIDATION_ERROR",
        )

    top_k = body.get("top_k", 4)
    filter_doc_id = body.get("filter_doc_id")
    search_mode = body.get("search_mode", "hybrid")
    chat_history = body.get("chat_history")
    use_mmr = bool(body.get("use_mmr", False))

    try:
        top_k = int(top_k)
        if top_k < 1 or top_k > 20:
            top_k = 4
    except (ValueError, TypeError):
        top_k = 4

    try:
        # 3. Execute RAG query against S3 Vectors and Amazon Nova
        result = pipeline.query(
            question=str(question).strip(),
            top_k=top_k,
            search_mode=search_mode,
            filter_doc_id=filter_doc_id,
            chat_history=chat_history,
            use_mmr=use_mmr,
        )

        # 4. Attach request audit information
        result["caller"] = {
            "username": auth_ctx.username,
            "groups": auth_ctx.groups,
        }

        logger.info(
            f"Query processed successfully for user '{auth_ctx.username}' in "
            f"{result['metrics']['total_latency_ms']}ms with {len(result['citations'])} citations."
        )

        return success_response(data=result, status_code=200)

    except Exception as e:
        logger.error(f"Error handling query: {str(e)}", exc_info=True)
        return error_response(
            message=f"Internal query processing error: {str(e)}",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        )
