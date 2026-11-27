"""
AWS Lambda Ingestion Handler for GroundedOps.
Handles document ingestion triggered by:
  1. S3 ObjectCreated events (automated asynchronous ingestion when docs are uploaded)
  2. API Gateway POST /ingest (secured synchronous direct ingestion API)
"""

import json
import os
import urllib.parse
from typing import Any, Dict
import boto3

from ..core.rag_pipeline import RAGPipeline
from ..utils.auth_validator import extract_auth_context
from ..utils.logger import get_logger
from ..utils.response import error_response, success_response

logger = get_logger("groundedops.ingest_handler")

# Initialize pipeline as reusable Lambda singleton across warm invocations
pipeline = RAGPipeline()
s3_client = boto3.client("s3")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda entry point for document ingestion.
    """
    logger.info("Ingest handler invoked", extra={"extra_fields": {"event_keys": list(event.keys())}})

    try:
        # Case 1: S3 Event Trigger (asynchronous file upload to S3 raw document bucket)
        if "Records" in event and event["Records"] and "s3" in event["Records"][0]:
            return handle_s3_event(event)

        # Case 2: API Gateway POST /ingest
        return handle_api_gateway_event(event)

    except Exception as e:
        logger.error(f"Unhandled ingestion error: {str(e)}", exc_info=True)
        return error_response(
            message=f"Ingestion failed: {str(e)}",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        )


def handle_s3_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process files uploaded directly to the raw documentation S3 bucket."""
    processed = []
    for record in event["Records"]:
        s3_data = record["s3"]
        bucket_name = s3_data["bucket"]["name"]
        raw_key = s3_data["object"]["key"]
        key = urllib.parse.unquote_plus(raw_key)

        logger.info(f"Processing S3 object s3://{bucket_name}/{key}")

        # Fetch file content from S3
        resp = s3_client.get_object(Bucket=bucket_name, Key=key)
        body_bytes = resp["Body"].read()

        try:
            content_str = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Handle binary or encoded files gracefully
            content_str = body_bytes.decode("latin-1", errors="replace")

        doc_id = os.path.basename(key)
        metadata = {
            "source": f"s3://{bucket_name}/{key}",
            "s3_bucket": bucket_name,
            "s3_key": key,
            "size_bytes": str(len(body_bytes)),
        }

        ingest_result = pipeline.ingest_document(
            doc_id=doc_id,
            content=content_str,
            metadata=metadata,
        )
        processed.append(ingest_result)

    return {
        "status": "success",
        "processed_count": len(processed),
        "results": processed,
    }


def handle_api_gateway_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle synchronous REST API ingestion with Cognito authentication."""
    auth_ctx = extract_auth_context(event)
    logger.info(
        f"API Ingestion requested by user '{auth_ctx.username}' with groups {auth_ctx.groups}"
    )

    # Optional role check: require Admins or Engineers to ingest new documents
    if auth_ctx.groups and not (auth_ctx.is_admin() or auth_ctx.has_role("Engineers")):
        return error_response(
            message="Unauthorized: User does not have permission to ingest documentation.",
            status_code=403,
            error_code="FORBIDDEN",
        )

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
            message="Invalid JSON payload.",
            status_code=400,
            error_code="INVALID_JSON",
        )

    doc_id = body.get("doc_id")
    content = body.get("content")
    metadata = body.get("metadata", {})

    if not doc_id or not content:
        return error_response(
            message="Fields 'doc_id' and 'content' are required.",
            status_code=400,
            error_code="VALIDATION_ERROR",
        )

    metadata["uploaded_by"] = auth_ctx.username

    ingest_result = pipeline.ingest_document(
        doc_id=doc_id,
        content=content,
        metadata=metadata,
    )

    return success_response(
        data={
            "message": f"Document '{doc_id}' successfully indexed into S3 Vectors.",
            "details": ingest_result,
        },
        status_code=201,
    )
