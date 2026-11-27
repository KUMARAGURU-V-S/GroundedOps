"""
GroundedOps - Interactive Web Dashboard (Streamlit).
Evidence-based AI Knowledge Retrieval System powered by Amazon Bedrock (Amazon Nova)
and serverless S3 Vectors.
"""

import os
import sys
import time
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.chunker import MarkdownChunker
from src.core.embeddings import BedrockEmbeddings
from src.core.nova_client import AmazonNovaClient
from src.core.rag_pipeline import RAGPipeline
from src.core.vector_store import S3VectorStore

st.set_page_config(
    page_title="GroundedOps - AI Knowledge Retrieval",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .citation-card {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    .score-badge {
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .metric-box {
        background: #F1F5F9;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_pipeline(model_id: str, mock_mode: bool):
    embeddings = BedrockEmbeddings(mock_mode=mock_mode)
    nova = AmazonNovaClient(model_id=model_id, mock_mode=mock_mode)
    vector_store = S3VectorStore()
    return RAGPipeline(
        embeddings=embeddings,
        nova_client=nova,
        vector_store=vector_store,
        chunker=MarkdownChunker(),
    )


# Sidebar Configuration
st.sidebar.image(
    "https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/AWS-Dark.svg",
    width=60,
)
st.sidebar.title("Configuration")

mock_mode = st.sidebar.checkbox(
    "Offline / Mock Mode",
    value=os.environ.get("MOCK_BEDROCK", "true").lower() == "true",
    help="Runs pipeline using local embeddings & mocks when AWS Bedrock credentials are not present.",
)

nova_model = st.sidebar.selectbox(
    "Amazon Nova Model",
    options=[
        "amazon.nova-micro-v1:0",
        "amazon.nova-lite-v1:0",
        "amazon.nova-pro-v1:0",
    ],
    index=0,
    help="Select the Amazon Bedrock foundation model for grounded reasoning.",
)

top_k = st.sidebar.slider("Top-K Retrieved Chunks", min_value=1, max_value=8, value=4)
sim_threshold = st.sidebar.slider(
    "Minimum Similarity Threshold", min_value=0.1, max_value=0.8, value=0.25, step=0.05
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Architecture Highlights:**
    - ⚡ **Amazon Bedrock**: Amazon Nova Micro/Lite
    - 📦 **S3 Vectors**: Serverless vector store
    - 🔒 **Amazon Cognito & IAM**: Zero-trust auth
    - 🌐 **Amazon API Gateway**: Serverless endpoints
    """
)

# Header
st.markdown('<div class="main-title">🛡️ GroundedOps – AI Knowledge Retrieval System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Serverless RAG pipeline providing verifiable, evidence-grounded answers from internal engineering documentation.</div>',
    unsafe_allow_html=True,
)

pipeline = load_pipeline(model_id=nova_model, mock_mode=mock_mode)
pipeline.top_k = top_k
pipeline.similarity_threshold = sim_threshold

tabs = st.tabs(["🔍 Knowledge Search", "📤 Document Ingestion", "📊 S3 Vectors Index & Stats"])

with tabs[0]:
    st.subheader("Query Internal Documentation")

    sample_questions = [
        "What are the steps to execute a failover on the Aurora PostgreSQL cluster?",
        "What is the token expiration and group hierarchy for Amazon Cognito authentication?",
        "How do I remediate an OOMKilled exit code 137 pod in Kubernetes?",
        "What are the SOC-2 requirements for data encryption at rest and in transit?",
    ]

    selected_sample = st.selectbox("Select a sample engineering question:", ["-- Select --"] + sample_questions)
    default_q = "" if selected_sample == "-- Select --" else selected_sample

    user_query = st.text_input(
        "Ask a technical question:",
        value=default_q,
        placeholder="e.g. What is the command to drain a Kubernetes worker node?",
    )

    if st.button("Retrieve Grounded Answer", type="primary") and user_query:
        with st.spinner("Embedding query, querying S3 Vectors, and synthesizing answer with Amazon Nova..."):
            res = pipeline.query(user_query, top_k=top_k)

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 💬 Grounded Response")
            st.markdown(res["answer"])

            st.markdown("### 📑 Evidence Citations")
            citations = res.get("citations", [])
            if citations:
                for c in citations:
                    st.markdown(
                        f"""
                        <div class="citation-card">
                            <strong>Citation #{c['citation_id']}:</strong> {c['doc_title']} 
                            <span class="score-badge">Similarity: {c['score']}</span><br>
                            <em>Section:</em> <code>{c['section']}</code> | <em>Chunk:</em> <code>{c['chunk_id']}</code><br>
                            <p style="margin-top: 6px; color: #475569;">"{c['excerpt']}"</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("No verified citations found for this query.")

        with col2:
            st.markdown("### ⏱️ Performance Metrics")
            metrics = res["metrics"]
            st.metric("Total Latency", f"{metrics['total_latency_ms']:.1f} ms")
            st.metric("Query Embedding", f"{metrics['embedding_latency_ms']:.1f} ms")
            st.metric("S3 Vector Search", f"{metrics['retrieval_latency_ms']:.1f} ms")
            st.metric("Amazon Nova Synthesis", f"{metrics['generation_latency_ms']:.1f} ms")
            st.metric("Confidence Score", f"{res['confidence_score']:.2f}")

            with st.expander("Retrieved Context Chunks"):
                for ctx in res.get("retrieved_context", []):
                    st.write(f"**{ctx['doc_title']} - {ctx['section']}** (Score: {ctx['score']})")
                    st.text(ctx["content"][:300] + "...")

with tabs[1]:
    st.subheader("Ingest New Documentation")
    doc_id_input = st.text_input("Document Identifier (e.g. `redis_cluster_runbook.md`)")
    doc_content_input = st.text_area("Document Content (Markdown / Text)", height=250)

    if st.button("Chunk, Embed & Store in S3 Vectors") and doc_id_input and doc_content_input:
        with st.spinner("Processing document..."):
            result = pipeline.ingest_document(
                doc_id=doc_id_input,
                content=doc_content_input,
                metadata={"uploaded_via": "Streamlit Dashboard"},
            )
        st.success(f"Successfully indexed '{doc_id_input}' into S3 Vectors!")
        st.json(result)

with tabs[2]:
    st.subheader("S3 Vectors Status & Catalog")
    stats = pipeline.get_pipeline_stats()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Indexed Documents", stats["indexed_documents_count"])
    col_b.metric("Total Vector Chunks", stats["total_chunks_count"])
    col_c.metric("Active Model", stats["generation_model"])

    st.write(f"**Storage Bucket**: `{stats['vector_bucket']}`")
    st.write(f"**Embedding Model**: `{stats['embedding_model']}`")

    if stats["documents"]:
        st.dataframe(stats["documents"], use_container_width=True)
    else:
        st.info("No documents indexed yet. Ingest documents from the Ingestion tab or run sample docs.")
