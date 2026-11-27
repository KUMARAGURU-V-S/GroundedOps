#!/usr/bin/env bash
set -euo pipefail

# Ingest sample docs using GroundedOps CLI
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"
SAMPLE_DIR="${ROOT_DIR}/sample_docs"

if [ -f "${ROOT_DIR}/.venv/bin/python3" ]; then
    PYTHON_CMD="${ROOT_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

echo "Ingesting internal sample documents into GroundedOps..."
"${PYTHON_CMD}" "${ROOT_DIR}/cli/groundedops_cli.py" ingest-dir "${SAMPLE_DIR}" "$@"
