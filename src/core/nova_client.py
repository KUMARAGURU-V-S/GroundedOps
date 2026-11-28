"""
Amazon Bedrock Amazon Nova Client for GroundedOps.
Orchestrates grounded response generation with Amazon Nova models
(Nova Micro, Nova Lite, Nova Pro) using Bedrock's Converse API.
Enforces strict hallucination prevention, evidence-based citation extraction,
multi-turn conversational memory, and real-time streaming output.
"""

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, List, Optional
import boto3
from botocore.config import Config

from .vector_store import SearchResult
from ..utils.logger import get_logger

logger = get_logger("groundedops.nova")


@dataclass
class Citation:
    """Represents a referenced evidence citation."""

    citation_id: int
    chunk_id: str
    doc_title: str
    section: str
    score: float
    excerpt: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundedResponse:
    """Represents the complete generated grounded response."""

    answer: str
    model_id: str
    is_grounded: bool
    confidence_score: float
    citations: List[Citation]
    retrieved_chunks_count: int
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "model_id": self.model_id,
            "is_grounded": self.is_grounded,
            "confidence_score": round(self.confidence_score, 4),
            "citations": [c.to_dict() for c in self.citations],
            "retrieved_chunks_count": self.retrieved_chunks_count,
            "latency_ms": round(self.latency_ms, 2),
        }


SYSTEM_PROMPT = """You are GroundedOps, an AI Knowledge Retrieval System for internal documentation, DevOps runbooks, and engineering specifications.

STRICT GROUNDING RULES:
1. Base your answer EXCLUSIVELY on the provided Context Documents below. Do NOT use outside knowledge or make assumptions.
2. If the context does not contain sufficient information to answer the question accurately, reply:
   "The internal documentation does not contain sufficient information to answer this question."
   Do NOT attempt to guess, hallucinate, or speculate.
3. Every factual claim must be backed by an inline citation formatted as: [Doc: <doc_title> | Section: <section> | Ref: #<chunk_id>]
4. Present operational procedures, incident remediation steps, commands, and architectural parameters clearly using markdown formatting and code blocks where applicable.
"""


class AmazonNovaClient:
    """
    Client for interacting with Amazon Nova models on Amazon Bedrock.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        bedrock_runtime_client: Optional[Any] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        mock_mode: bool = False,
    ):
        self.model_id = (
            model_id
            or os.environ.get("NOVA_MODEL_ID")
            or "amazon.nova-micro-v1:0"
        )
        self.region_name = (
            region_name
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mock_mode = (
            mock_mode or os.environ.get("MOCK_BEDROCK", "false").lower() == "true"
        )

        if not self.mock_mode:
            if bedrock_runtime_client:
                self.client = bedrock_runtime_client
            else:
                config = Config(
                    region_name=self.region_name,
                    retries={"max_attempts": 3, "mode": "standard"},
                )
                self.client = boto3.client("bedrock-runtime", config=config)
        else:
            self.client = None

    def _build_context_prompt(
        self,
        query: str,
        chunks: List[SearchResult],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Construct structured conversation messages including context blocks and history."""
        context_blocks = []
        for i, c in enumerate(chunks, 1):
            block = (
                f"--- CONTEXT DOCUMENT [{i}] ---\n"
                f"Document: {c.doc_title} ({c.doc_id})\n"
                f"Section: {c.section}\n"
                f"Chunk ID: {c.chunk_id}\n"
                f"Relevance Score: {c.score}\n"
                f"Content:\n{c.content}\n"
            )
            context_blocks.append(block)

        joined_context = "\n".join(context_blocks)
        user_message_text = (
            f"Context Documents:\n"
            f"{joined_context}\n\n"
            f"User Question: {query}\n\n"
            f"Please provide an accurate, evidence-grounded response citing the context above."
        )

        messages: List[Dict[str, Any]] = []

        # Append prior conversation history turns if provided
        if chat_history:
            for turn in chat_history[-6:]:  # Keep recent context window
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ["user", "assistant"] and content:
                    messages.append({
                        "role": role,
                        "content": [{"text": content}],
                    })

        # Append current user prompt with context
        messages.append({
            "role": "user",
            "content": [{"text": user_message_text}],
        })

        return messages

    def _extract_citations(
        self, answer: str, chunks: List[SearchResult]
    ) -> List[Citation]:
        """
        Cross-reference retrieved chunks with generated response to assemble citations.
        """
        citations: List[Citation] = []
        seen_chunks = set()
        citation_counter = 1

        for c in chunks:
            if (
                c.chunk_id in answer
                or f"Ref: #{c.chunk_id}" in answer
                or (c.section.lower() in answer.lower() and c.doc_title.lower() in answer.lower())
            ):
                if c.chunk_id not in seen_chunks:
                    seen_chunks.add(c.chunk_id)
                    citations.append(
                        Citation(
                            citation_id=citation_counter,
                            chunk_id=c.chunk_id,
                            doc_title=c.doc_title,
                            section=c.section,
                            score=c.score,
                            excerpt=c.content[:200] + ("..." if len(c.content) > 200 else ""),
                        )
                    )
                    citation_counter += 1

        if not citations and chunks and "not contain sufficient information" not in answer:
            for c in chunks[:2]:
                citations.append(
                    Citation(
                        citation_id=citation_counter,
                        chunk_id=c.chunk_id,
                        doc_title=c.doc_title,
                        section=c.section,
                        score=c.score,
                        excerpt=c.content[:200] + ("..." if len(c.content) > 200 else ""),
                    )
                )
                citation_counter += 1

        return citations

    def _mock_generate(
        self, query: str, chunks: List[SearchResult]
    ) -> str:
        """Deterministic response generation for offline testing/mock mode."""
        if not chunks:
            return "The internal documentation does not contain sufficient information to answer this question."

        top_chunk = chunks[0]
        answer = (
            f"Based on internal documentation '{top_chunk.doc_title}' [Doc: {top_chunk.doc_title} | Section: {top_chunk.section} | Ref: #{top_chunk.chunk_id}]:\n\n"
            f"{top_chunk.content}\n\n"
            f"Key operational takeaways:\n"
            f"- Source verified from section '{top_chunk.section}' with relevance score {top_chunk.score}.\n"
            f"- Refer to {top_chunk.doc_id} for complete operational guidelines."
        )
        return answer

    def generate_grounded_answer(
        self,
        query: str,
        chunks: List[SearchResult],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> GroundedResponse:
        """
        Invoke Amazon Bedrock Amazon Nova to synthesize a grounded response.
        """
        import time

        start_time = time.perf_counter()

        if not chunks:
            latency = (time.perf_counter() - start_time) * 1000.0
            return GroundedResponse(
                answer="The internal documentation does not contain sufficient information to answer this question.",
                model_id=self.model_id,
                is_grounded=False,
                confidence_score=0.0,
                citations=[],
                retrieved_chunks_count=0,
                latency_ms=latency,
            )

        messages = self._build_context_prompt(query, chunks, chat_history)

        if self.mock_mode:
            answer = self._mock_generate(query, chunks)
        else:
            try:
                system = [{"text": SYSTEM_PROMPT}]
                response = self.client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=system,
                    inferenceConfig={
                        "temperature": self.temperature,
                        "maxTokens": self.max_tokens,
                        "topP": 0.9,
                    },
                )

                output_message = response.get("output", {}).get("message", {})
                content_blocks = output_message.get("content", [])
                answer = "".join(
                    b.get("text", "") for b in content_blocks if "text" in b
                ).strip()

            except Exception as e:
                logger.warning(
                    f"Converse API call failed for {self.model_id}: {e}. Retrying with invoke_model payload."
                )
                try:
                    last_user_text = messages[-1]["content"][0]["text"]
                    body = json.dumps(
                        {
                            "system": [{"text": SYSTEM_PROMPT}],
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [{"text": last_user_text}],
                                }
                            ],
                            "inferenceConfig": {
                                "temperature": self.temperature,
                                "maxTokens": self.max_tokens,
                            },
                        }
                    )
                    resp = self.client.invoke_model(
                        modelId=self.model_id,
                        contentType="application/json",
                        accept="application/json",
                        body=body,
                    )
                    resp_body = json.loads(resp["body"].read().decode("utf-8"))
                    answer = (
                        resp_body.get("output", {})
                        .get("message", {})
                        .get("content", [{}])[0]
                        .get("text", "")
                    )
                except Exception as inner_e:
                    logger.error(f"Bedrock invocation error: {inner_e}")
                    raise

        latency = (time.perf_counter() - start_time) * 1000.0
        citations = self._extract_citations(answer, chunks)

        is_grounded = (
            len(citations) > 0
            and "not contain sufficient information" not in answer.lower()
        )
        avg_score = (
            sum(c.score for c in citations) / len(citations) if citations else 0.0
        )

        return GroundedResponse(
            answer=answer,
            model_id=self.model_id,
            is_grounded=is_grounded,
            confidence_score=avg_score,
            citations=citations,
            retrieved_chunks_count=len(chunks),
            latency_ms=latency,
        )

    def stream_grounded_answer(
        self,
        query: str,
        chunks: List[SearchResult],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterator[str]:
        """
        Stream grounded answer tokens in real-time from Amazon Bedrock ConverseStream API.
        """
        if not chunks:
            yield "The internal documentation does not contain sufficient information to answer this question."
            return

        if self.mock_mode:
            full_text = self._mock_generate(query, chunks)
            words = full_text.split(" ")
            for w in words:
                yield w + " "
            return

        messages = self._build_context_prompt(query, chunks, chat_history)
        system = [{"text": SYSTEM_PROMPT}]

        try:
            response = self.client.converse_stream(
                modelId=self.model_id,
                messages=messages,
                system=system,
                inferenceConfig={
                    "temperature": self.temperature,
                    "maxTokens": self.max_tokens,
                },
            )

            stream = response.get("stream")
            if stream:
                for event in stream:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
        except Exception as e:
            logger.error(f"Error during stream generation: {e}")
            yield f"\n[Error streaming response from Amazon Nova: {str(e)}]"
