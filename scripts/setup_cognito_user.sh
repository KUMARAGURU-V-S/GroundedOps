#!/usr/bin/env bash
set -euo pipefail

# GroundedOps Cognito Test User Setup Script
ENVIRONMENT="${1:-dev}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
STACK_NAME="groundedops-${ENVIRONMENT}"

USER_EMAIL="${2:-engineer@internal.corp}"
USER_PASSWORD="${3:-GroundedOps2026!}"
USER_GROUP="${4:-Engineers}"

echo "Fetching Cognito User Pool ID from CloudFormation stack '${STACK_NAME}'..."
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
  --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolClientId'].OutputValue" \
  --output text)

echo "User Pool ID: ${USER_POOL_ID}"
echo "Client ID:    ${CLIENT_ID}"

echo "Creating user '${USER_EMAIL}'..."
aws cognito-idp admin-create-user \
  --user-pool-id "${USER_POOL_ID}" \
  --username "${USER_EMAIL}" \
  --user-attributes Name=email,Value="${USER_EMAIL}" Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region "${AWS_REGION}" || true

echo "Setting permanent password..."
aws cognito-idp admin-set-user-password \
  --user-pool-id "${USER_POOL_ID}" \
  --username "${USER_EMAIL}" \
  --password "${USER_PASSWORD}" \
  --permanent \
  --region "${AWS_REGION}"

echo "Adding user to group '${USER_GROUP}'..."
aws cognito-idp admin-add-user-to-group \
  --user-pool-id "${USER_POOL_ID}" \
  --username "${USER_EMAIL}" \
  --group-name "${USER_GROUP}" \
  --region "${AWS_REGION}"

echo "Obtaining initial JWT authentication token..."
AUTH_RESP=$(aws cognito-idp admin-initiate-auth \
  --user-pool-id "${USER_POOL_ID}" \
  --client-id "${CLIENT_ID}" \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME="${USER_EMAIL}",PASSWORD="${USER_PASSWORD}" \
  --region "${AWS_REGION}")

ID_TOKEN=$(echo "${AUTH_RESP}" | python3 -c "import sys, json; print(json.load(sys.stdin)['AuthenticationResult']['IdToken'])")

echo ""
echo "=========================================================="
echo " Authentication Successful!"
echo " User:   ${USER_EMAIL}"
echo " Group:  ${USER_GROUP}"
echo " Bearer ID Token for API Gateway (use in Authorization header):"
echo "=========================================================="
echo "${ID_TOKEN}"
