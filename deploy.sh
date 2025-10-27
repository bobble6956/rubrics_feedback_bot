#!/bin/bash
set -e

# --- Configuration ---
# This script assumes your terraform files are in a './terraform' directory
# relative to this script.
TERRAFORM_DIR="./terraform"
SERVICE_NAME="essay-feedback-bot"
LOCATION="global" # Hardcoded 'global' as per your app.py

# --- Check for DATA_STORE_ID ---
if [ -z "$DATA_STORE_ID" ]; then
    echo "ERROR: DATA_STORE_ID environment variable is not set."
    echo "Please set it before running this script:"
    echo ""
    echo "  export DATA_STORE_ID=\"your-data-store-id-from-gcp-console\""
    echo ""
    echo "Aborting."
    exit 1
fi

echo "--- Fetching Infrastructure Outputs from Terraform ---"

# Get outputs from the terraform directory
TF_REGION=$(cd $TERRAFORM_DIR && terraform output -raw region)
TF_SERVICE_ACCOUNT_EMAIL=$(cd $TERRAFORM_DIR && terraform output -raw service_account_email)
TF_PROJECT_ID=$(cd $TERRAFORM_DIR && terraform output -raw project_id)
TF_VERTEX_AI_LOCATION=$(cd $TERRAFORM_DIR && terraform output -raw vertex_ai_location)

echo "Project ID:           $TF_PROJECT_ID"
echo "Region:               $TF_REGION"
echo "Service Account:    $TF_SERVICE_ACCOUNT_EMAIL"
echo "Vertex AI Location:   $TF_VERTEX_AI_LOCATION"
echo "Data Store ID:        $DATA_STORE_ID (from env)"
echo ""
echo "--- Starting Cloud Run Deployment ---"

# --- Run the gcloud deploy command ---
# This command runs from the root directory (where Dockerfile is)
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region "$TF_REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --timeout "120" \
  --service-account "$TF_SERVICE_ACCOUNT_EMAIL" \
  --set-env-vars "PROJECT_ID=$TF_PROJECT_ID" \
  --set-env-vars "DATA_STORE_ID=$DATA_STORE_ID" \
  --set-env-vars "LOCATION=$LOCATION" \
  --set-env-vars "VERTEX_AI_LOCATION=$TF_VERTEX_AI_LOCATION" \
  --set-env-vars "MIN_KEYWORD_SCORE_THRESHOLD=1.0"

echo "--- Deployment Complete ---"
