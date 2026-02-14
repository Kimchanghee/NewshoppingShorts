#!/bin/bash
# SSMaker Backend - Cloud Run Deployment Script (secure defaults)
set -euo pipefail

# Configuration (can be overridden via environment variables)
PROJECT_ID="${PROJECT_ID:-project-d0118f2c-58f4-4081-864}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ssmaker-auth-api}"
CLOUD_SQL_CONN="${CLOUDSQL_CONN:-${PROJECT_ID}:${REGION}:ssmaker-auth}"

# Must be explicitly set by deployment operator.
if [[ -z "${ALLOWED_ORIGINS:-}" ]]; then
  echo "ERROR: ALLOWED_ORIGINS is required (e.g. https://app.example.com)" >&2
  exit 1
fi

if [[ -z "${PAYMENT_API_BASE_URL:-}" ]]; then
  echo "ERROR: PAYMENT_API_BASE_URL is required (e.g. https://<service>.run.app)" >&2
  exit 1
fi

# Secret names can be overridden per environment.
DB_PASSWORD_SECRET="${DB_PASSWORD_SECRET:-ssmaker-db-password}"
JWT_SECRET_KEY_SECRET="${JWT_SECRET_KEY_SECRET:-ssmaker-jwt-secret}"
ADMIN_API_KEY_SECRET="${ADMIN_API_KEY_SECRET:-ssmaker-admin-api-key}"
BILLING_KEY_ENCRYPTION_KEY_SECRET="${BILLING_KEY_ENCRYPTION_KEY_SECRET:-ssmaker-billing-key-encryption-key}"
PAYAPP_USERID_SECRET="${PAYAPP_USERID_SECRET:-ssmaker-payapp-userid}"
PAYAPP_LINKKEY_SECRET="${PAYAPP_LINKKEY_SECRET:-ssmaker-payapp-linkkey}"
PAYAPP_LINKVAL_SECRET="${PAYAPP_LINKVAL_SECRET:-ssmaker-payapp-linkval}"

echo "=== SSMaker Backend Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "CloudSQL: $CLOUD_SQL_CONN"
echo ""

gcloud config set project "$PROJECT_ID"

# NOTE:
# - Cloud Run auth (IAM) is intentionally left open here so desktop clients can call the API.
# - Security must be enforced at the application layer (JWT + admin API key verification).
echo "Building and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances "$CLOUD_SQL_CONN" \
  --set-env-vars "DB_HOST=127.0.0.1,DB_PORT=3306,DB_USER=ssmaker_user,DB_NAME=ssmaker_auth,CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONN},ENVIRONMENT=production,ALLOWED_ORIGINS=${ALLOWED_ORIGINS},PAYMENT_API_BASE_URL=${PAYMENT_API_BASE_URL}" \
  --set-secrets "DB_PASSWORD=${DB_PASSWORD_SECRET}:latest,JWT_SECRET_KEY=${JWT_SECRET_KEY_SECRET}:latest,ADMIN_API_KEY=${ADMIN_API_KEY_SECRET}:latest,BILLING_KEY_ENCRYPTION_KEY=${BILLING_KEY_ENCRYPTION_KEY_SECRET}:latest,PAYAPP_USERID=${PAYAPP_USERID_SECRET}:latest,PAYAPP_LINKKEY=${PAYAPP_LINKKEY_SECRET}:latest,PAYAPP_LINKVAL=${PAYAPP_LINKVAL_SECRET}:latest" \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60

echo ""
echo "=== Deployment Complete ==="
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)"
