# GroundedOps – AI Knowledge Retrieval System

[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-orange?logo=amazon-aws)](https://aws.amazon.com/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Nova%20%7C%20Titan-blue?logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![S3 Vectors](https://img.shields.io/badge/Storage-S3%20Vectors-green?logo=amazons3)](https://aws.amazon.com/s3/)
[![Cognito Secured](https://img.shields.io/badge/Security-Cognito%20%2B%20IAM-red?logo=jsonwebtokens)](https://aws.amazon.com/cognito/)
[![IaC CloudFormation](https://img.shields.io/badge/IaC-CloudFormation%20%2F%20SAM-lightgrey?logo=cloudformation)](https://aws.amazon.com/cloudformation/)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![Test Suite](https://img.shields.io/badge/Tests-16%20Passed-brightgreen?logo=pytest)](tests/)

> **GroundedOps** is an enterprise-grade, serverless Retrieval-Augmented Generation (RAG) system built with **Amazon S3**, **AWS Lambda**, **Amazon Bedrock (Amazon Nova)**, and **S3 Vectors**. It provides strictly evidence-based, verifiable answers from internal documentation, engineering runbooks, and architectural specifications with zero standing infrastructure costs.

---

## 🎯 Key Capabilities

- **Serverless RAG Pipeline**: Fully automated document chunking, embedding generation with Amazon Titan Embeddings v2, and grounded synthesis via Amazon Bedrock Amazon Nova (Micro, Lite, and Pro).
- **S3 Vectors Architecture**: Replaces expensive managed vector databases (OpenSearch Serverless, Pinecone) with an optimized, serverless vector store native to Amazon S3—reducing standing hosting costs by over **90%** ($0.00/month idle cost).
- **Strict Grounding & Hallucination Refusal**: Enforces deterministic prompt templates, contextual chunk headers, and strict refusal rules. If internal documentation does not contain the answer, GroundedOps safely refuses to speculate.
- **Evidence Citations**: Every generated response includes verifiable inline citations, document IDs, section names, chunk identifiers, and similarity confidence scores.
- **Enterprise Security**: Secured perimeter with **Amazon API Gateway**, **Amazon Cognito User Pools** (JWT token authorizer with RBAC groups: `Admins`, `Engineers`, `Auditors`), and least-privilege **AWS IAM** execution roles.
- **Infrastructure as Code (IaC)**: Turnkey deployment via AWS CloudFormation / SAM templates.
- **Developer Tools**: Production-ready Python CLI, interactive Streamlit dashboard, and standalone web client.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion["Document Ingestion Pipeline"]
        A["DevOps Runbooks / Markdown (.md, .pdf)"] --> B["Amazon S3 Raw Bucket"]
        B -->|S3 Event / API Ingest| C["AWS Lambda: IngestHandler"]
        C --> D["Markdown Chunking & Section Tracker"]
        D --> E["Amazon Bedrock: Titan Embeddings v2"]
        E --> F[("Amazon S3 Vectors Store")]
        F --> F1["catalog.json"]
        F --> F2["docs/{doc_id}/chunks.json"]
        F --> F3["index/all_vectors.json"]
    end

    subgraph Query["Grounded Query Pipeline"]
        G["Engineer / On-Call Operator"] -->|Cognito Bearer JWT| H["Amazon API Gateway"]
        H -->|Cognito Authorizer| I["AWS Lambda: QueryHandler"]
        I --> J["Embed Query (Bedrock Titan)"]
        J --> K["S3 Vectors Cosine Similarity Search"]
        F3 -.->|Top-K Chunks| K
        K --> L["Context Assembly & Grounding Rules"]
        L --> M["Amazon Bedrock: Amazon Nova"]
        M --> N["Citation & Evidence Extraction"]
        N --> O["Grounded Response + Telemetry"]
        O --> H --> G
    end
```

---

## 💰 Why S3 Vectors? Cost Advantage Analysis

Traditional RAG systems require continuous cluster provisioning, resulting in high baseline monthly costs even with zero queries:

| Metric / Vector Store | Amazon OpenSearch Serverless | Pinecone (Standard) | AWS Aurora pgvector | **GroundedOps (S3 Vectors)** |
| :--- | :--- | :--- | :--- | :--- |
| **Minimum Idle Units** | 2 Search OCUs + 2 Index OCUs | 1 Pod | 0.5 ACU Serverless | **Zero (Pure Serverless)** |
| **Hourly Idle Cost** | $0.96 / hr | ~$0.096 / hr | ~$0.06 / hr | **$0.00 / hr** |
| **Monthly Standing Cost**| **~$691.20 / mo** | **~$70.00 / mo** | **~$43.20 / mo** | **$0.00 / mo** |
| **Storage Cost (100 MB)**| Included in OCU | Included in Pod | ~$0.01 / mo | **$0.002 / mo** |
| **Query Cost (10k req)** | Included in OCU | Included in Pod | Compute ACUs | **~$0.20 (Lambda + S3)** |
| **Total Monthly Cost**   | **~$691.20** | **~$70.00** | **~$43.20** | **~$0.20 (99.9% Savings)** |

---

## 📂 Repository Structure

```
GroundedOps/
├── cloudformation/
│   ├── template.yaml            # AWS CloudFormation / SAM infrastructure template
│   └── parameters-dev.json      # Development deployment parameters
├── src/
│   ├── handlers/
│   │   ├── ingest_handler.py    # S3 event & API Gateway ingestion Lambda handler
│   │   ├── query_handler.py     # API Gateway grounded query Lambda handler
│   │   └── health_handler.py    # System health & diagnostics Lambda handler
│   ├── core/
│   │   ├── chunker.py           # Markdown & section-aware text chunker
│   │   ├── embeddings.py        # Amazon Bedrock embedding generator (Titan / Nova)
│   │   ├── vector_store.py      # S3 Vectors store & cosine similarity search engine
│   │   ├── nova_client.py       # Amazon Bedrock Amazon Nova client & citation parser
│   │   └── rag_pipeline.py      # Coordinated end-to-end RAG orchestrator
│   └── utils/
│       ├── logger.py            # Structured JSON CloudWatch logger
│       ├── response.py          # API Gateway CORS response formatter
│       └── auth_validator.py    # Cognito claims & role-based access validator
├── cli/
│   └── groundedops_cli.py       # Developer & admin CLI tool
├── web/
│   ├── app.py                   # Streamlit interactive dashboard
│   ├── static/
│   │   ├── index.html           # Standalone HTML5/JS web application
│   │   └── style.css            # Custom CSS styling
│   └── README.md
├── sample_docs/
│   ├── 01_database_failover_runbook.md
│   ├── 02_microservices_architecture_spec.md
│   ├── 03_kubernetes_incident_response.md
│   └── 04_security_compliance_soc2.md
├── scripts/
│   ├── deploy.sh                # Automated CloudFormation deployment script
│   ├── setup_cognito_user.sh    # Cognito test user onboarding script
│   ├── ingest_sample_docs.sh    # Bulk document ingestion script
│   └── run_local_demo.sh        # Complete local demonstration script
├── tests/
│   ├── conftest.py              # Pytest fixtures & Moto S3 mocks
│   ├── unit/                    # Unit tests for core modules & handlers
│   └── integration/             # Integration tests for end-to-end grounding
├── template.yaml                # Root SAM deployment template
├── Makefile                     # Build & test automation targets
├── requirements.txt             # Lambda runtime dependencies
└── requirements-dev.txt         # Testing and development dependencies
```

---

## 🚀 Quickstart Guide

### 1. Local Setup & Testing (Offline Mode)

You can run GroundedOps locally without active AWS credentials using deterministic mock mode:

```bash
# Clone the repository
git clone https://github.com/KUMARAGURU-V-S/GroundedOps.git
cd GroundedOps

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run complete test suite (all 16 tests passing)
pytest -v
```

### 2. Run the Local Demonstration

Execute the automated local demonstration script to ingest sample documentation, index into S3 Vectors, and run grounded queries with citation extraction:

```bash
./scripts/run_local_demo.sh
```

Sample output:
```text
==========================================================
 Starting GroundedOps Local Demonstration
==========================================================
[Step 1] Ingesting Internal Engineering Documentation...
  ✓ 01_database_failover_runbook.md -> 8 chunks stored in S3 Vectors
  ✓ 04_security_compliance_soc2.md -> 4 chunks stored in S3 Vectors
  ✓ 02_microservices_architecture_spec.md -> 6 chunks stored in S3 Vectors
  ✓ 03_kubernetes_incident_response.md -> 7 chunks stored in S3 Vectors

[Step 2] Listing Indexed Documents in S3 Vectors Store...
Document ID                         Title                                    Chunks  
-------------------------------------------------------------------------------------
01_database_failover_runbook.md     Aurora PostgreSQL Multi-AZ Database Fa   8       
04_security_compliance_soc2.md      Cloud Security & SOC-2 Type II Complia   4       
02_microservices_architecture_spec.md Enterprise Microservices Architecture    6       
03_kubernetes_incident_response.md  EKS Kubernetes Incident Response Stand   7       

[Step 3] Query: What are the exact commands to failover the Aurora PostgreSQL cluster?
--- Grounded Answer ---
Based on internal documentation 'Aurora PostgreSQL Multi-AZ Database Failover Runbook' [Doc: Aurora PostgreSQL Multi-AZ Database Failover Runbook | Section: 1. Overview and Incident Criteria | Ref: #01_database_failover_runbook.md#c1]:

This runbook defines the emergency operational procedure for handling primary database failures...

--- Evidence Citations ---
  [1] Aurora PostgreSQL Multi-AZ Database Failover Runbook | Section: 1. Overview and Incident Criteria | Score: 0.2752 | Chunk: #01_database_failover_runbook.md#c1
```

---

## 💻 CLI Usage Guide

The `groundedops_cli.py` tool provides command-line control over ingestion and retrieval:

```bash
# Ingest a single file
python3 cli/groundedops_cli.py ingest-file sample_docs/01_database_failover_runbook.md

# Ingest an entire directory of runbooks
python3 cli/groundedops_cli.py ingest-dir sample_docs/

# Query with Amazon Nova
python3 cli/groundedops_cli.py query "How do I fix an exit code 137 OOMKilled error?"

# Query specifying model and top-k
python3 cli/groundedops_cli.py query "What is the token expiration for Cognito?" --model amazon.nova-lite-v1:0 --top-k 3

# List indexed documents in S3 Vectors
python3 cli/groundedops_cli.py list-docs

# View pipeline health and storage statistics
python3 cli/groundedops_cli.py stats
```

---

## 🌐 Web Dashboard

### Streamlit Application
```bash
streamlit run web/app.py
```
Features:
- Real-time question answering with inline citation badges.
- Model selector: Amazon Nova Micro, Nova Lite, and Nova Pro.
- Latency waterfall metrics (Embedding vs S3 Retrieval vs Nova Generation).
- Document ingestion portal and S3 Vectors catalog viewer.

### Standalone HTML5 Client
Serve the zero-dependency web interface:
```bash
python3 -m http.server 8080 --directory web/static
```
Open `http://localhost:8080` in your browser.

---

## ☁️ AWS CloudFormation Deployment

### 1. Deploy Infrastructure
Deploy the serverless stack (S3 Buckets, Cognito User Pool, IAM Roles, Lambda Functions, API Gateway):

```bash
# Set your target AWS region
export AWS_REGION="us-east-1"

# Deploy via automated script
./scripts/deploy.sh dev
```

Alternatively, deploy using AWS SAM CLI:
```bash
sam build
sam deploy --guided
```

### 2. Onboard a Cognito Test User
Create an authenticated test engineer and obtain a JWT token:

```bash
./scripts/setup_cognito_user.sh dev engineer@internal.corp "GroundedOps2026!" "Engineers"
```

### 3. Ingest Runbooks into Production S3
Upload files directly to the created S3 Document Bucket, or ingest via API Gateway:
```bash
export API_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/dev"
export TOKEN="<jwt-token-from-setup-script>"

curl -X POST "${API_URL}/ingest" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "01_database_failover_runbook.md",
    "content": "# Aurora Database Failover Runbook\n\n## Failover Steps\nRun: aws rds failover-db-cluster..."
  }'
```

### 4. Query the API
```bash
curl -X POST "${API_URL}/query" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the command to failover the Aurora database?",
    "top_k": 4
  }'
```

Response:
```json
{
  "status": "success",
  "data": {
    "question": "What is the command to failover the Aurora database?",
    "answer": "Based on internal documentation: To execute a failover...",
    "is_grounded": true,
    "confidence_score": 0.89,
    "model_id": "amazon.nova-micro-v1:0",
    "citations": [
      {
        "citation_id": 1,
        "doc_title": "Aurora PostgreSQL Multi-AZ Database Failover Runbook",
        "section": "Step-by-Step Failover Procedure",
        "score": 0.89,
        "chunk_id": "01_database_failover_runbook.md#c3",
        "excerpt": "aws rds failover-db-cluster --db-cluster-identifier aurora-prod-cluster-01..."
      }
    ],
    "metrics": {
      "total_latency_ms": 342.1,
      "embedding_latency_ms": 41.5,
      "retrieval_latency_ms": 18.2,
      "generation_latency_ms": 282.4
    }
  }
}
```

---

## 🔒 Security & IAM Specifications

- **Amazon Cognito User Pool**: Pre-configured user pool with strict password policies and group mapping (`Admins` for ingestion/management, `Engineers` for queries).
- **API Gateway Cognito Authorizer**: Pre-flight authorization verifies RS256 JWT signature and expiration before requests reach Lambda handlers.
- **AWS IAM Least Privilege**:
  - `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` restricted to `arn:aws:s3:::groundedops-documents-*` and `arn:aws:s3:::groundedops-vectors-*`.
  - `bedrock:InvokeModel` and `bedrock:Converse` scoped to Amazon Nova and Titan foundation models.
- **S3 Bucket Hardening**: Public access block enforced, SSE-AES256 encryption enabled, versioning configured.

---

## 🧪 Testing

The repository includes a test suite covering unit tests, mocks, and integration flows:

```bash
# Run all tests
pytest -v

# Run with test coverage report
pytest --cov=src --cov-report=term-missing tests/
```

Test summary:
- `tests/unit/test_chunker.py`: Heading extraction, sliding window segmentation, and boundary handling.
- `tests/unit/test_embeddings.py`: L2 normalization, dimension checks, and feature hashing.
- `tests/unit/test_vector_store.py`: S3 index storage, cosine similarity ranking, and catalog deletion.
- `tests/unit/test_nova_client.py`: Grounded generation, citation parsing, and hallucination refusal.
- `tests/unit/test_handlers.py`: API Gateway and S3 event Lambda proxy handlers.
- `tests/integration/test_end_to_end_local.py`: Full document ingestion and retrieval validation.

---

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
