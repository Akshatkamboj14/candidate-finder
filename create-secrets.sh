#!/bin/bash

# Script to create Kubernetes secrets from .env file

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating Kubernetes secrets from .env file...${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found in current directory${NC}"
    exit 1
fi

# Extract sensitive variables for secrets
echo -e "${YELLOW}Creating secrets...${NC}"
kubectl create secret generic app-secrets \
    --from-literal=AWS_ACCESS_KEY_ID="$(grep '^AWS_ACCESS_KEY_ID=' .env | cut -d'=' -f2)" \
    --from-literal=AWS_SECRET_ACCESS_KEY="$(grep '^AWS_SECRET_ACCESS_KEY=' .env | cut -d'=' -f2)" \
    --from-literal=GITHUB_TOKEN="$(grep '^GITHUB_TOKEN=' .env | cut -d'=' -f2)" \
    --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ Secrets created successfully!${NC}"

# Verify creation
echo -e "${YELLOW}Verifying secrets...${NC}"
echo "Secrets:"
kubectl get secrets app-secrets -o jsonpath='{.data}' | jq -r 'keys[]' 2>/dev/null || kubectl get secrets app-secrets -o jsonpath='{.data}' | grep -o '"[^"]*"' | tr -d '"'
