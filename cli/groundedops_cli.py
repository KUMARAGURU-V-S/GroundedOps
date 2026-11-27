#!/usr/bin/env python3
"""
GroundedOps CLI - Administrative & Developer Tool.
Command-line interface to ingest internal documentation, query knowledge base,
inspect S3 Vectors, and test evidence-grounded responses.
"""

import argparse
import glob
import json
import os
import sys
from typing import Optional

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.rag_pipeline import RAGPipeline
from src.core.embeddings import BedrockEmbeddings
from src.core.nova_client import AmazonNovaClient
from src.core.vector_store import S3VectorStore


def format_ansi(text: str, color_code: str) -> str:
    """Format text with ANSI escape colors."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{color_code}m{text}\033[0m"


def bold(text: str) -> str:
    return format_ansi(text, "1")


def cyan(text: str) -> str:
    return format_ansi(text, "36")


def green(text: str) -> str:
    return format_ansi(text, "32")


def yellow(text: str) -> str:
    return format_ansi(text, "33")


def red(text: str) -> str:
    return format_ansi(text, "31")


def get_pipeline(mock: bool = False, model_id: Optional[str] = None) -> RAGPipeline:
    embeddings = BedrockEmbeddings(mock_mode=mock)
    nova = AmazonNovaClient(model_id=model_id, mock_mode=mock)
    vector_store = S3VectorStore()
    return RAGPipeline(
        embeddings=embeddings,
        nova_client=nova,
        vector_store=vector_store,
    )


def cmd_ingest_file(args):
    pipeline = get_pipeline(mock=args.mock)
    filepath = args.filepath

    if not os.path.exists(filepath):
        print(red(f"Error: File not found: {filepath}"))
        sys.exit(1)

    doc_id = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    print(cyan(f"Ingesting file: {filepath} ({len(content)} characters)..."))
    res = pipeline.ingest_document(
        doc_id=doc_id,
        content=content,
        metadata={"source_path": filepath},
    )

    print(green(f"✓ Successfully indexed '{doc_id}' into S3 Vectors!"))
    print(f"  - Document Title: {bold(res['title'])}")
    print(f"  - Chunks Created: {res['chunks_count']}")
    print(f"  - Storage Key:    {res['s3_key']}")
    print(
        f"  - Latency:        Chunking: {res['timing_ms']['chunking']}ms | "
        f"Embedding: {res['timing_ms']['embedding']}ms | "
        f"S3 Storage: {res['timing_ms']['storage']}ms"
    )


def cmd_ingest_dir(args):
    pipeline = get_pipeline(mock=args.mock)
    directory = args.directory

    if not os.path.isdir(directory):
        print(red(f"Error: Directory not found: {directory}"))
        sys.exit(1)

    patterns = ["*.md", "*.txt", "*.json"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(directory, pat)))

    if not files:
        print(yellow(f"No files matching patterns ({patterns}) found in {directory}"))
        return

    print(cyan(f"Found {len(files)} documents to ingest from {directory}..."))
    for fp in files:
        doc_id = os.path.basename(fp)
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        res = pipeline.ingest_document(
            doc_id=doc_id,
            content=content,
            metadata={"source_dir": directory},
        )
        print(green(f"  ✓ {doc_id} -> {res['chunks_count']} chunks stored in S3 Vectors"))

    print(bold(green("\nAll documents ingested successfully!")))


def cmd_query(args):
    pipeline = get_pipeline(mock=args.mock, model_id=args.model)
    if hasattr(args, "min_score") and args.min_score is not None:
        pipeline.similarity_threshold = args.min_score
    question = args.question

    print(cyan(f"\n[Question]: {bold(question)}"))
    print(f"Retrieving grounded evidence using S3 Vectors and Amazon Nova ({pipeline.nova_client.model_id})...\n")

    res = pipeline.query(question=question, top_k=args.top_k)

    print(bold("--- Grounded Answer ---"))
    print(res["answer"])
    print("\n" + bold("--- Evidence Citations ---"))
    if res["citations"]:
        for c in res["citations"]:
            print(
                f"  [{c['citation_id']}] {bold(c['doc_title'])} "
                f"| Section: {cyan(c['section'])} "
                f"| Score: {green(str(c['score']))} "
                f"| Chunk: #{c['chunk_id']}"
            )
            print(f"      Excerpt: \"{c['excerpt'].strip()}\"\n")
    else:
        print(yellow("  No citations matched (unverified response or no evidence found)."))

    print(bold("--- Latency & Metrics ---"))
    metrics = res["metrics"]
    print(
        f"  Total: {metrics['total_latency_ms']}ms | "
        f"Embedding: {metrics['embedding_latency_ms']}ms | "
        f"S3 Vector Retrieval: {metrics['retrieval_latency_ms']}ms | "
        f"Nova Generation: {metrics['generation_latency_ms']}ms"
    )
    print(f"  Grounded: {res['is_grounded']} | Confidence: {res['confidence_score']}\n")


def cmd_list(args):
    pipeline = get_pipeline(mock=args.mock)
    docs = pipeline.vector_store.list_indexed_documents()
    print(cyan(f"\nIndexed Documents in S3 Vectors ({pipeline.vector_store.bucket_name}):"))
    if not docs:
        print(yellow("  (No documents found)"))
        return

    print(f"{'Document ID':<35} {'Title':<40} {'Chunks':<8}")
    print("-" * 85)
    for d in docs:
        print(f"{d['doc_id']:<35} {d['title'][:38]:<40} {d['chunk_count']:<8}")
    print(f"\nTotal Documents: {len(docs)} | Total Chunks: {sum(d['chunk_count'] for d in docs)}\n")


def cmd_stats(args):
    pipeline = get_pipeline(mock=args.mock)
    stats = pipeline.get_pipeline_stats()
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="GroundedOps: AI Knowledge Retrieval CLI"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock/offline mode without calling live AWS Bedrock/S3",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest file
    p_ingest = subparsers.add_parser("ingest-file", help="Ingest a single document")
    p_ingest.add_argument("filepath", help="Path to markdown/text file")
    p_ingest.set_defaults(func=cmd_ingest_file)

    # Ingest directory
    p_dir = subparsers.add_parser("ingest-dir", help="Ingest all files in a directory")
    p_dir.add_argument("directory", help="Path to directory")
    p_dir.set_defaults(func=cmd_ingest_dir)

    # Query
    p_query = subparsers.add_parser("query", help="Ask a question against internal docs")
    p_query.add_argument("question", help="Question string")
    p_query.add_argument("--top-k", type=int, default=4, help="Top-K chunks to retrieve")
    p_query.add_argument(
        "--min-score",
        type=float,
        default=0.10,
        help="Minimum similarity score threshold (default: 0.10)",
    )
    p_query.add_argument(
        "--model",
        default="amazon.nova-micro-v1:0",
        help="Nova model ID (e.g. amazon.nova-micro-v1:0, amazon.nova-lite-v1:0)",
    )
    p_query.set_defaults(func=cmd_query)

    # List
    p_list = subparsers.add_parser("list-docs", help="List all indexed documents")
    p_list.set_defaults(func=cmd_list)

    # Stats
    p_stats = subparsers.add_parser("stats", help="Get pipeline statistics")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
