"""
CloudWatch Telemetry & Metrics Emitter for GroundedOps.
Publishes operational metrics for latency, retrieval quality, and hallucination refusals
to Amazon CloudWatch under the 'GroundedOps/RAG' namespace.
"""

import os
from typing import Any, Dict, List, Optional
import boto3
from botocore.config import Config

from .logger import get_logger

logger = get_logger("groundedops.telemetry")


class MetricsEmitter:
    """Publishes custom CloudWatch metrics for GroundedOps."""

    def __init__(
        self,
        namespace: str = "GroundedOps/RAG",
        region_name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.namespace = namespace
        self.region_name = (
            region_name
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.enabled = (
            enabled
            if enabled is not None
            else os.environ.get("ENABLE_METRICS", "false").lower() == "true"
        )
        self.cw = None

        if self.enabled:
            try:
                config = Config(region_name=self.region_name)
                self.cw = boto3.client("cloudwatch", config=config)
            except Exception as e:
                logger.warning(f"Could not initialize CloudWatch client: {e}")
                self.enabled = False

    def emit_query_metrics(
        self,
        metrics: Dict[str, Any],
        is_grounded: bool,
        confidence_score: float,
        environment: str = "dev",
    ) -> None:
        """Publish query performance and grounding accuracy telemetry."""
        if not self.enabled or not self.cw:
            return

        dimensions = [
            {"Name": "Environment", "Value": environment},
            {"Name": "System", "Value": "GroundedOps"},
        ]

        metric_data: List[Dict[str, Any]] = [
            {
                "MetricName": "TotalQueryLatency",
                "Value": float(metrics.get("total_latency_ms", 0.0)),
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "RetrievalLatency",
                "Value": float(metrics.get("retrieval_latency_ms", 0.0)),
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "GenerationLatency",
                "Value": float(metrics.get("generation_latency_ms", 0.0)),
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "ConfidenceScore",
                "Value": float(confidence_score),
                "Unit": "None",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "RetrievedChunksCount",
                "Value": float(metrics.get("retrieved_chunks_count", 0)),
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "HallucinationRefusalCount",
                "Value": 1.0 if not is_grounded else 0.0,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
        ]

        try:
            self.cw.put_metric_data(Namespace=self.namespace, MetricData=metric_data)
        except Exception as e:
            logger.warning(f"Failed to publish CloudWatch metrics: {e}")
