#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Candidate Finder to Kubernetes...${NC}"

# Function to check if command succeeded
check_command() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: $1 failed${NC}"
        exit 1
    fi
}

# Check prerequisites
echo -e "${BLUE}🔍 Checking prerequisites...${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
    exit 1
fi

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ docker is not installed or not in PATH${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found. Please create one first.${NC}"
    exit 1
fi

# Check if k8s directory exists
if [ ! -d "k8s" ]; then
    echo -e "${RED}❌ Error: k8s directory not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Create secrets from .env file
echo -e "${YELLOW}� Creating secrets from .env file...${NC}"
kubectl create secret generic app-secrets --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f - 
check_command "Creating secrets"

# Build Docker images with better error handling
echo -e "${YELLOW}🔨 Building Docker images...${NC}"

echo "Building backend image..."
docker build -t candidate-finder-backend:latest ./backend
check_command "Building backend image"

echo "Building frontend image..."
docker build -t candidate-finder-frontend:latest ./frontend
check_command "Building frontend image"

echo -e "${GREEN}✅ Docker images built successfully${NC}"

# Apply Kubernetes manifests in correct order
echo -e "${YELLOW}📦 Applying Kubernetes manifests...${NC}"

# Apply storage components first
echo "Applying storage configuration..."
kubectl apply -f k8s/storageclass.yaml 
kubectl apply -f k8s/storage.yaml 

# Apply configmaps
echo "Applying configmaps..."
kubectl apply -f k8s/configmap.yaml 
kubectl apply -f k8s/app-configmap.yaml 

# Apply backend (needs to be up first for frontend to connect)
echo "Deploying backend..."
kubectl apply -f k8s/backend.yaml 
check_command "Deploying backend"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/backend-deployment 
check_command "Backend deployment readiness"

# Apply frontend
echo "Deploying frontend..."
kubectl apply -f k8s/frontend.yaml 
check_command "Deploying frontend"

# Wait for frontend to be ready
echo "Waiting for frontend to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/frontend-deployment 
check_command "Frontend deployment readiness"

# Show status
echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Deployment status:${NC}"
kubectl get pods,services 

echo ""
echo -e "${BLUE}🔍 Pod details:${NC}"
kubectl get pods  -o wide

# Get node IP for external access
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')
if [ -z "$NODE_IP" ]; then
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
fi

# Get frontend service nodeport
FRONTEND_PORT=$(kubectl get service frontend-service  -o jsonpath='{.spec.ports[0].nodePort}')

echo ""
echo -e "${GREEN}🌐 Access URLs:${NC}"
echo -e "  Frontend: http://${NODE_IP}:${FRONTEND_PORT}"
echo -e "  Backend API: http://${NODE_IP}:$(kubectl get service backend-service  -o jsonpath='{.spec.ports[0].nodePort}')"

echo ""
echo -e "${YELLOW}📋 Useful commands:${NC}"
echo "  Check logs: "
echo "    Backend: kubectl logs -f deployment/backend-deployment "
echo "    Frontend: kubectl logs -f deployment/frontend-deployment "
echo "  Scale applications:"
echo "    Backend: kubectl scale deployment backend-deployment --replicas=3 "
echo "    Frontend: kubectl scale deployment frontend-deployment --replicas=2 "
echo "  Port forward (for testing):"
echo "    Frontend: kubectl port-forward service/frontend-service 8080:80 "
echo "    Backend: kubectl port-forward service/backend-service 8001:8000 "
echo "  Monitor resources:"
echo "    kubectl top pods "
echo "    kubectl describe pods "
echo ""
echo -e "${GREEN}🎉 Happy Kubernetes deployment! Your K8s Assistant is now running in the cluster!${NC}"