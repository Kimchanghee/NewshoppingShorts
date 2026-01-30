#!/bin/bash
# SSMaker Backend - Cloud Run Deployment Script

# Configuration
PROJECT_ID="project-d0118f2c-58f4-4081-864"
REGION="us-central1"
SERVICE_NAME="ssmaker-auth-api"
CLOUD_SQL_INSTANCE="ssmaker-auth"
CLOUD_SQL_CONNECTION="${PROJECT_ID}:${REGION}:${CLOUD_SQL_INSTANCE}"

echo "=== SSMaker Backend Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Build and deploy to Cloud Run
echo "Building and deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances $CLOUD_SQL_CONNECTION \
  --set-env-vars "DB_HOST=127.0.0.1" \
  --set-env-vars "DB_PORT=3306" \
  --set-env-vars "DB_USER=ssmaker_user" \
  --set-env-vars "DB_NAME=ssmaker_auth" \
  --set-env-vars "CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION}" \
  --set-env-vars "ENVIRONMENT=production" \
  --set-env-vars "ALLOWED_ORIGINS=*" \
  --set-env-vars "SSMAKER_API_KEY=ssmaker" \
  --set-secrets "DB_PASSWORD=ssmaker-db-password:latest" \
  --set-secrets "JWT_SECRET_KEY=ssmaker-jwt-secret:latest" \
  --set-secrets "ADMIN_API_KEY=ssmaker-admin-api-key:latest" \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60

echo ""
echo "=== Deployment Complete ==="
echo "Run: gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)'"
