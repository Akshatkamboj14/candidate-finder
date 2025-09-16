#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 Cleaning up Kubernetes resources...${NC}"

# Delete deployments and services
kubectl delete -f k8s/frontend.yaml
kubectl delete -f k8s/backend.yaml

# Delete all resources
kubectl delete -f k8s/backend.yaml --ignore-not-found=true
kubectl delete -f k8s/frontend.yaml --ignore-not-found=true
kubectl delete -f k8s/configmap.yaml --ignore-not-found=true
kubectl delete -f k8s/app-configmap.yaml --ignore-not-found=true
kubectl delete -f k8s/storage.yaml --ignore-not-found=true

# Delete secrets
kubectl delete secret app-secrets --ignore-not-found=true

# Alternative: delete by resource type
# kubectl delete deployment backend-deployment frontend-deployment
# kubectl delete service backend-service frontend-service
# kubectl delete configmap app-config nginx-config
# kubectl delete secret app-secrets

echo -e "${GREEN}✅ Cleanup completed!${NC}"

# Verify cleanup
echo -e "${YELLOW}📊 Remaining resources:${NC}"
kubectl get pods,services,configmaps,secrets | grep -E "(backend|frontend|app-)"
