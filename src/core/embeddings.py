"""
Amazon Bedrock Embedding Service for GroundedOps.
Generates normalized vector representations using Amazon Bedrock foundation models
(e.g., Amazon Titan Embeddings v2, Titan v1, or Nova Embeddings).
"""

import hashlib
import json
import math
import os
import re
from typing import Any, Dict, List, Optional
import boto3
from botocore.config import Config

from ..utils.logger import get_logger

logger = get_logger("groundedops.embeddings")

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "is", "are", "was", "were", "what", "how", "when", "where", "which",
    "who", "why", "it", "this", "that", "these", "those", "from", "as", "be",
}


class BedrockEmbeddings:
    """
    Client for generating text embeddings via Amazon Bedrock Runtime.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        dimensions: int = 1024,
        normalize: bool = True,
        bedrock_client: Optional[Any] = None,
        mock_mode: bool = False,
    ):
        self.model_id = (
            model_id
            or os.environ.get("EMBEDDING_MODEL_ID")
            or "amazon.titan-embed-text-v2:0"
        )
        self.region_name = (
            region_name
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.dimensions = dimensions
        self.normalize = normalize
        self.mock_mode = (
            mock_mode or os.environ.get("MOCK_BEDROCK", "false").lower() == "true"
        )

        if not self.mock_mode:
            if bedrock_client:
                self.client = bedrock_client
            else:
                config = Config(
                    region_name=self.region_name,
                    retries={"max_attempts": 3, "mode": "standard"},
                )
                self.client = boto3.client("bedrock-runtime", config=config)
        else:
            self.client = None

    def _l2_normalize(self, vector: List[float]) -> List[float]:
        """Normalize vector to unit length so dot product == cosine similarity."""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]

    def _mock_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic mock embedding using term & n-gram feature hashing
        with stop-word filtering so that texts with overlapping substantive terms
        have realistic positive cosine similarity.
        """
        vec = [0.0] * self.dimensions
        raw_words = re.findall(r"\w+", text.lower())
        words = [w for w in raw_words if w not in STOP_WORDS]
        if not words:
            return vec

        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimensions
            vec[idx] += 1.0

        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i+1]}"
            h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimensions
            vec[idx] += 1.5

        return self._l2_normalize(vec) if self.normalize else vec

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single string."""
        if not text or not text.strip():
            return [0.0] * self.dimensions

        if self.mock_mode:
            return self._mock_embedding(text)

        try:
            if "titan-embed-text-v2" in self.model_id:
                body = json.dumps(
                    {
                        "inputText": text,
                        "dimensions": self.dimensions,
                        "normalize": self.normalize,
                    }
                )
            elif "titan-embed" in self.model_id:
                body = json.dumps({"inputText": text})
            else:
                body = json.dumps({"inputText": text})

            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            response_body = json.loads(response["body"].read().decode("utf-8"))
            embedding = response_body.get("embedding", [])

            if self.normalize and "titan-embed-text-v2" not in self.model_id:
                embedding = self._l2_normalize(embedding)

            return embedding

        except Exception as e:
            logger.error(
                f"Error generating embedding with model {self.model_id}: {str(e)}"
            )
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of strings."""
        return [self.embed_text(t) for t in texts]
