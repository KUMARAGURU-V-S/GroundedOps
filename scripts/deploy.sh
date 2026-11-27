#!/usr/bin/env bash
set -euo pipefail

# GroundedOps Automated CloudFormation / SAM Deployment Script
ENVIRONMENT="${1:-dev}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
STACK_NAME="groundedops-${ENVIRONMENT}"

echo "=========================================================="
echo " Deploying GroundedOps to AWS (${ENVIRONMENT})"
echo " Region: ${AWS_REGION} | Stack: ${STACK_NAME}"
echo "=========================================================="

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed or not in PATH."
    exit 1
fi

echo "Verifying AWS caller identity..."
aws sts get-caller-identity

# Build and deploy using SAM if available, otherwise CloudFormation package & deploy
if command -v sam &> /dev/null; then
    echo "Building SAM application..."
    sam build --template-file template.yaml

    echo "Deploying SAM stack..."
    sam deploy \
      --stack-name "${STACK_NAME}" \
      --region "${AWS_REGION}" \
      --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
      --parameter-overrides Environment="${ENVIRONMENT}" \
      --no-fail-on-empty-changeset \
      --resolve-s3
else
    echo "SAM CLI not found. Packaging and deploying using AWS CloudFormation directly..."
    DEPLOYMENT_BUCKET="groundedops-cfn-artifacts-$(aws sts get-caller-identity --query Account --output text)-${AWS_REGION}"

    # Ensure deployment bucket exists
    if ! aws s3api head-bucket --bucket "${DEPLOYMENT_BUCKET}" 2>/dev/null; then
        echo "Creating deployment bucket: ${DEPLOYMENT_BUCKET}..."
        aws s3 mb "s3://${DEPLOYMENT_BUCKET}" --region "${AWS_REGION}"
    fi

    echo "Packaging template..."
    aws cloudformation package \
      --template-file template.yaml \
      --s3-bucket "${DEPLOYMENT_BUCKET}" \
      --output-template-file .packaged-template.yaml

    echo "Deploying CloudFormation stack..."
    aws cloudformation deploy \
      --template-file .packaged-template.yaml \
      --stack-name "${STACK_NAME}" \
      --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
      --parameter-overrides Environment="${ENVIRONMENT}" \
      --region "${AWS_REGION}" \
      --no-fail-on-empty-changeset
fi

echo ""
echo "=========================================================="
echo " Stack Outputs:"
echo "=========================================================="
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo "Deployment complete!"
