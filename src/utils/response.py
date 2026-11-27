"""
API Gateway Response Utilities for GroundedOps.
Provides standardized JSON responses with CORS headers.
"""

import json
from typing import Any, Dict, Optional


def build_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Build standard API Gateway Lambda proxy integration response.
    """
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, default=str),
    }


def success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Helper for successful responses."""
    payload = {"status": "success", "data": data}
    return build_response(status_code, payload)


def error_response(
    message: str,
    status_code: int = 400,
    error_code: str = "BAD_REQUEST",
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    """Helper for error responses."""
    payload = {
        "status": "error",
        "error": {
            "code": error_code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return build_response(status_code, payload)
