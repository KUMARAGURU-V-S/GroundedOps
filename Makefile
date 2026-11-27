.PHONY: help install test demo lint clean deploy

PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin

help:
	@echo "GroundedOps - AI Knowledge Retrieval System"
	@echo "-------------------------------------------"
	@echo "make install    - Create virtual environment and install dependencies"
	@echo "make test       - Run pytest test suite"
	@echo "make demo       - Run local CLI demonstration"
	@echo "make web        - Launch Streamlit web dashboard"
	@echo "make deploy     - Deploy CloudFormation stack to AWS"
	@echo "make clean      - Remove temporary and cached files"

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt

test:
	$(BIN)/pytest -v

demo:
	./scripts/run_local_demo.sh

web:
	$(BIN)/streamlit run web/app.py

clean:
	rm -rf .pytest_cache .local_s3_vectors __pycache__ src/**/__pycache__ tests/**/__pycache__
