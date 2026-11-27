#!/usr/bin/env bash
set -euo pipefail

# Runs a complete local demo of GroundedOps:
# 1. Ingests all 4 internal sample documents
# 2. Lists indexed documents in S3 Vectors
# 3. Runs 3 realistic DevOps/SRE questions with citations
# 4. Asks an out-of-domain question to demonstrate hallucination refusal

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

if [ -f "${ROOT_DIR}/.venv/bin/python3" ]; then
    PYTHON_CMD="${ROOT_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

export MOCK_BEDROCK=true
export LOCAL_VECTOR_STORE=true
export VECTORS_BUCKET_NAME="groundedops-local-vectors"

echo "=========================================================="
echo " Starting GroundedOps Local Demonstration"
echo " (Running with Mock Bedrock & Local S3 Vectors Store)"
echo "=========================================================="

echo -e "\n[Step 1] Ingesting Internal Engineering Documentation..."
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" --mock ingest-dir "${ROOT_DIR}/sample_docs"

echo -e "\n[Step 2] Listing Indexed Documents in S3 Vectors Store..."
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" --mock list-docs

echo -e "\n[Step 3] Query 1: Database Incident Response"
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" --mock query "What are the exact commands to failover the Aurora PostgreSQL cluster and reload PgBouncer?"

echo -e "\n[Step 4] Query 2: Kubernetes Incident Response"
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" --mock query "How do I fix an exit code 137 OOMKilled error and drain a worker node?"

echo -e "\n[Step 5] Query 3: Hallucination Prevention Test (Out-of-Domain Query)"
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" --mock query "What is the secret recipe for baking chocolate chip cookies?" --min-score 0.15

echo -e "\n=========================================================="
echo " GroundedOps Demonstration Completed Successfully!"
echo "=========================================================="
