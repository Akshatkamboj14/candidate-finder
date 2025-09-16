#!/bin/bash

# Test Kubernetes deployment

echo "☸️  Testing Kubernetes Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check cluster connectivity
echo ""
echo -e "${YELLOW}🔍 Testing cluster connectivity...${NC}"
kubectl cluster-info && echo -e "${GREEN}✅ Cluster reachable${NC}" || (echo -e "${RED}❌ Cannot reach cluster${NC}" && exit 1)

# Test 2: Check if secrets exist
echo ""
echo -e "${YELLOW}🔐 Checking secrets...${NC}"
kubectl get secret app-secrets &>/dev/null && echo -e "${GREEN}✅ Secrets exist${NC}" || echo -e "${RED}❌ Secrets missing - run ./deploy.sh${NC}"

# Test 3: Check if configmaps exist
echo ""
echo -e "${YELLOW}📝 Checking configmaps...${NC}"
kubectl get configmap app-config &>/dev/null && echo -e "${GREEN}✅ ConfigMaps exist${NC}" || echo -e "${RED}❌ ConfigMaps missing${NC}"

# Test 4: Check if PVCs exist
echo ""
echo -e "${YELLOW}💾 Checking storage...${NC}"
kubectl get pvc chroma-storage sqlite-storage &>/dev/null && echo -e "${GREEN}✅ Storage ready${NC}" || echo -e "${RED}❌ Storage missing${NC}"

# Test 5: Check deployment status
echo ""
echo -e "${YELLOW}🚀 Checking deployments...${NC}"
kubectl get deployments

# Test 6: Check pod status
echo ""
echo -e "${YELLOW}📦 Checking pods...${NC}"
kubectl get pods -l app=backend -o wide
kubectl get pods -l app=frontend -o wide

# Test 7: Check services
echo ""
echo -e "${YELLOW}🌐 Checking services...${NC}"
kubectl get services

# Test 8: Get application URL
echo ""
echo -e "${YELLOW}🔗 Getting application URL...${NC}"
NODE_PORT=$(kubectl get service frontend-service -o jsonpath='{.spec.ports[0].nodePort}')
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')

if [ -z "$NODE_IP" ]; then
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
fi

echo -e "${GREEN}🌐 Application URL: http://${NODE_IP}:${NODE_PORT}${NC}"

# Test 9: Test health endpoints
echo ""
echo -e "${YELLOW}🔍 Testing health endpoints...${NC}"

# Port forward for testing
kubectl port-forward service/backend-service 8080:8000 &
PF_PID=$!
sleep 3

# Test backend health
curl -f http://localhost:8080/health &>/dev/null && echo -e "${GREEN}✅ Backend health check passed${NC}" || echo -e "${RED}❌ Backend health check failed${NC}"

# Kill port forward
kill $PF_PID 2>/dev/null

# Test 10: Show logs if there are issues
echo ""
echo -e "${YELLOW}📋 Recent pod logs:${NC}"
echo "Backend logs:"
kubectl logs -l app=backend --tail=10 --since=1m

echo ""
echo "Frontend logs:"
kubectl logs -l app=frontend --tail=10 --since=1m

echo ""
echo -e "${GREEN}✅ Kubernetes testing completed!${NC}"
echo ""
echo -e "${YELLOW}🛠️  Useful testing commands:${NC}"
echo "  kubectl logs -f deployment/backend-deployment"
echo "  kubectl logs -f deployment/frontend-deployment"
echo "  kubectl port-forward service/frontend-service 8080:80"
echo "  kubectl port-forward service/backend-service 8081:8000"
echo "  kubectl exec -it deployment/backend-deployment -- /bin/bash"
