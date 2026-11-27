"""Unit tests for Lambda Handlers."""

import json
from src.handlers.health_handler import lambda_handler as health_handler
from src.handlers.ingest_handler import lambda_handler as ingest_handler
from src.handlers.query_handler import lambda_handler as query_handler


def test_health_handler(mock_s3_bucket):
    event = {}
    resp = health_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "success"
    assert "data" in body


def test_query_handler_validation_error():
    event = {"body": "{}"}
    resp = query_handler(event, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_ingest_handler_validation_error():
    event = {"body": json.dumps({"doc_id": "test.md"})}
    resp = ingest_handler(event, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_query_handler_success(mock_s3_bucket):
    # First ingest a document
    ingest_event = {
        "body": json.dumps({
            "doc_id": "runbook.md",
            "content": "# Runbook\n\n## Failover\nExecute failover immediately using aws rds failover."
        })
    }
    ingest_resp = ingest_handler(ingest_event, None)
    assert ingest_resp["statusCode"] == 201

    # Query the document
    query_event = {
        "body": json.dumps({
            "question": "How to execute failover?"
        })
    }
    query_resp = query_handler(query_event, None)
    assert query_resp["statusCode"] == 200
    body = json.loads(query_resp["body"])
    assert body["status"] == "success"
    assert "answer" in body["data"]
