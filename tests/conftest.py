"""
Pytest configuration and shared fixtures for GroundedOps.
"""

import os
import boto3
import pytest
from moto import mock_aws

# Ensure test environment variables
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["VECTORS_BUCKET_NAME"] = "test-groundedops-vectors"
os.environ["EMBEDDING_MODEL_ID"] = "amazon.titan-embed-text-v2:0"
os.environ["NOVA_MODEL_ID"] = "amazon.nova-micro-v1:0"
os.environ["MOCK_BEDROCK"] = "true"


@pytest.fixture
def sample_markdown():
    return """# Disaster Recovery Plan

## Overview
This document specifies the disaster recovery plan for our mission-critical services.
The recovery point objective is 5 minutes.

## Database Failover
To failover the primary database, execute:
```bash
aws rds failover-db-cluster --db-cluster-identifier prod-cluster
```
Drain connection pools immediately.

## Escalation
If recovery exceeds 15 minutes, page the Tier-3 engineering lead.
"""


@pytest.fixture
def mock_s3_bucket():
    """Moto S3 bucket fixture."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = os.environ["VECTORS_BUCKET_NAME"]
        s3.create_bucket(Bucket=bucket_name)
        yield s3, bucket_name
