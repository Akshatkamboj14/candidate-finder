# Kubernetes Deployment Guide

This guide explains how to deploy the Candidate Finder ap2. Run the deployment (this will creat### 1. Create Secrets from .env file

```bash
# Create secrets from your .env file
kubectl create secret generic app-secrets --from-env-file=.env
```

### 2. Build Docker Images secrets from your .env file):
   ```bash
   ./deploy.sh
   ```

The deployment script will:
- Check for `.env` file existence
- Create Kubernetes secrets from your `.env` file using: `kubectl create secret generic app-secrets --from-env-file=.env`
- Build Docker images
- Deploy all Kubernetes manifestsatio### 3. Deploy to Kubernetes

```bash
# Apply ConfigMaps
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/app-configmap.yaml

# Deploy backend and frontend
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
```tes.

## Architecture

- **Backend**: FastAPI application running on port 8000 (ClusterIP service)
- **Frontend**: React app with nginx reverse proxy on port 80 (NodePort service on 30080)
- **Reverse Proxy**: nginx routes `/api/*` requests to backend and serves static React files

## Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- Docker
- kubectl configured to connect to your cluster
- `.env` file in the root directory with your environment variables

## Environment Variables Setup

Your `.env` file should contain both sensitive and non-sensitive variables. The deployment script will automatically:
- Create Kubernetes **secrets** from your `.env` file for sensitive data (AWS keys, GitHub tokens)
- Use **configmaps** for non-sensitive configuration (regions, model IDs, etc.)

Example `.env` file structure:
```bash
# Sensitive (will become secrets)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
GITHUB_TOKEN=your-github-token

# Non-sensitive (handled by configmaps)
BEDROCK_REGION=us-east-1
BEDROCK_COMPLETION_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
# ... other config
```
- `.env` file in the project root with required environment variables

## Environment Variables Setup

The application uses Kubernetes Secrets and ConfigMaps to manage environment variables:

## Configuration

### Environment Variables from .env
The application uses a `.env` file for configuration. When you run the deployment script, it automatically creates Kubernetes secrets from this file:

```bash
# This command is run automatically by deploy.sh
kubectl create secret generic app-secrets --from-env-file=.env
```

**Important**: Keep your `.env` file in `.gitignore` to prevent committing sensitive data.

### Manual Secret Creation
If you need to create secrets manually or update them:

```bash
# Create from .env file
kubectl create secret generic app-secrets --from-env-file=.env

# Or create individual secrets
kubectl create secret generic app-secrets 
  --from-literal=AWS_ACCESS_KEY_ID=your-key 
  --from-literal=AWS_SECRET_ACCESS_KEY=your-secret 
  --from-literal=GITHUB_TOKEN=your-token
```

## Quick Deployment

1. Create your `.env` file with the required environment variables (see above)

2. Make the deployment scripts executable:
   ```bash
   chmod +x deploy.sh create-secrets.sh cleanup.sh
   ```

3. Run the deployment:
   ```bash
   ./deploy.sh
   ```

## Manual Deployment

### 1. Create Secrets and ConfigMaps

Create from .env file automatically:
```bash
./create-secrets.sh
```

Or manually create them:
```bash
# Create secrets
kubectl create secret generic app-secrets \
  --from-literal=AWS_ACCESS_KEY_ID=your-key \
  --from-literal=AWS_SECRET_ACCESS_KEY=your-secret \
  --from-literal=GITHUB_TOKEN=your-token

# Create configmap
kubectl create configmap app-config \
  --from-literal=BEDROCK_REGION=us-east-1 \
  --from-literal=DEBUG=true
  # ... add other config values
```

### 2. Build Docker Images

```bash
# Build backend image
docker build -t candidate-finder-backend:latest ./backend

# Build frontend image  
docker build -t candidate-finder-frontend:latest ./frontend
```

### 3. Deploy to Kubernetes

```bash
# Apply ConfigMaps
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/app-configmap.yaml

# Deploy backend and frontend
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
```

### 4. Check Deployment Status

```bash
# Check pods
kubectl get pods

# Check services
kubectl get services

# Check deployment status
kubectl get deployments
```

## Accessing the Application

### Frontend
The frontend is exposed via NodePort on port 30080:
```bash
# Get node IP
kubectl get nodes -o wide

# Access application at: http://<node-ip>:30080
```

### API Endpoints
The backend API is accessible through the frontend's reverse proxy:
- Direct API calls: `http://<node-ip>:30080/api/`
- Example: `http://<node-ip>:30080/api/health`

## Configuration

### Managing Secrets and ConfigMaps

**View current secrets and configmaps:**
```bash
# List secrets
kubectl get secrets

# View secret data (base64 encoded)
kubectl get secret app-secrets -o yaml

# List configmaps
kubectl get configmaps

# View configmap data
kubectl get configmap app-config -o yaml
```

**Update secrets:**
```bash
# Update from .env file
./create-secrets.sh

# Or update individual values
kubectl create secret generic app-secrets \
  --from-literal=AWS_ACCESS_KEY_ID=new-key \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Update configmaps:**
```bash
kubectl create configmap app-config \
  --from-literal=DEBUG=false \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Legacy Environment Variables Setup
If you prefer to add environment variables directly to the deployment instead of using the .env file approach, you can modify `k8s/backend.yaml`:

```yaml
env:
- name: DATABASE_URL
  value: "your-database-url"
- name: AWS_REGION
  value: "us-east-1"
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: aws-credentials
      key: access-key-id
```

### Secrets
For sensitive data, create Kubernetes secrets:

```bash
kubectl create secret generic aws-credentials \
  --from-literal=access-key-id=your-access-key \
  --from-literal=secret-access-key=your-secret-key
```

### Resource Limits
Current resource limits:
- **Backend**: 512Mi-1Gi memory, 250m-500m CPU
- **Frontend**: 256Mi-512Mi memory, 100m-200m CPU

Adjust these in the deployment files based on your needs.

## Scaling

### Scale Deployments
```bash
# Scale backend to 5 replicas
kubectl scale deployment backend-deployment --replicas=5

# Scale frontend to 3 replicas
kubectl scale deployment frontend-deployment --replicas=3
```

## Monitoring

### Health Checks
Both services have health check endpoints:
- Backend: `http://backend-service:8000/health`
- Frontend: `http://frontend-service/health`

### Logs
```bash
# Backend logs
kubectl logs -f deployment/backend-deployment

# Frontend logs  
kubectl logs -f deployment/frontend-deployment
```

## Troubleshooting

### Common Issues

1. **Images not found**: Ensure Docker images are built and available in your cluster
2. **Connection refused**: Check if services are running and endpoints are correct
3. **502 Bad Gateway**: Backend service might be down or unreachable

### Debug Commands
```bash
# Describe pod for detailed information
kubectl describe pod <pod-name>

# Execute into a pod for debugging
kubectl exec -it <pod-name> -- /bin/bash

# Check service endpoints
kubectl get endpoints
```

## Cleanup

Run the cleanup script:
```bash
./cleanup.sh
```

Or manually delete resources:
```bash
# Delete all resources
kubectl delete -f k8s/

# Or delete individual resources
kubectl delete deployment backend-deployment frontend-deployment
kubectl delete service backend-service frontend-service
kubectl delete configmap nginx-config app-config
kubectl delete secret app-secrets
```