#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Candidate Finder to Kubernetes...${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found. Please create one first.${NC}"
    exit 1
fi

# Create secrets from .env file
echo -e "${YELLOW}📝 Creating secrets from .env file...${NC}"
kubectl create secret generic app-secrets --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

# Build Docker images
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
echo "Building backend image..."
docker build -t candidate-finder-backend:latest ./backend

echo "Building frontend image..."
docker build -t candidate-finder-frontend:latest ./frontend

# Apply Kubernetes manifests
echo -e "${YELLOW}📦 Applying Kubernetes manifests...${NC}"
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/storageclass.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/app-configmap.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/.

# Show status
echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo "📊 Deployment status:"
kubectl get pods,services

echo ""
echo -e "${GREEN}🌐 Frontend is available at: http://<node-ip>:30080${NC}"
echo -e "${YELLOW}💡 To get node IP: kubectl get nodes -o wide${NC}"

# Show useful commands
echo ""
echo -e "${YELLOW}📋 Useful commands:${NC}"
echo "  Check logs: kubectl logs -f deployment/backend-deployment"
echo "  Scale backend: kubectl scale deployment backend-deployment --replicas=5"
echo "  Port forward (for testing): kubectl port-forward service/frontend-service 8080:80"