# Kubernetes Integration - Changes Summary

This document summarizes all the changes made to integrate your candidate-finder application with Kubernetes using secrets and configmaps.

## 🔄 **Modified Files**

### Backend Changes

#### 1. `/backend/app/main.py`
- **Added Kubernetes detection**: Checks for `KUBERNETES_SERVICE_HOST` environment variable
- **Enhanced environment loading**: Works with both .env files (development) and environment variables (Kubernetes)
- **Updated CORS**: Added wildcard and localhost origins for development and production
- **Added health check endpoint**: `/health` endpoint for Kubernetes liveness/readiness probes
- **Improved error handling**: Doesn't fail if .env file is missing in production

#### 2. `/backend/app/infrastructure/aws/vectorstore.py`
- **Fixed CHROMA_PERSIST_DIR usage**: Now properly uses environment variable
- **Auto-create directories**: Creates ChromaDB directory if it doesn't exist
- **Removed hardcoded paths**: Uses configurable path from environment

### Frontend Changes

#### 3. `/frontend/src/services/api.js`
- **Environment-aware API URLs**: Uses `/api` in production (nginx proxy) and full URL in development
- **Production compatibility**: Works with nginx reverse proxy in Kubernetes

### Kubernetes Manifests

#### 4. `/k8s/app-configmap.yaml` (New)
- **Non-sensitive configuration**: Bedrock settings, database URL, debug flags
- **Matches .env values**: Uses same configuration as your local environment

#### 5. `/k8s/backend.yaml`
- **Environment variables from secrets**: AWS credentials, GitHub token
- **Environment variables from configmaps**: Non-sensitive configuration
- **Persistent volumes**: Added volume mounts for ChromaDB and SQLite data
- **Health checks**: Uses the new `/health` endpoint

#### 6. `/k8s/storage.yaml` (New)
- **Persistent Volume Claims**: For ChromaDB (1Gi) and SQLite (500Mi) data
- **Data persistence**: Ensures data survives pod restarts

#### 7. `/deploy.sh`
- **Automatic secret creation**: Creates secrets from .env file
- **Storage deployment**: Applies persistent volume claims
- **Enhanced error checking**: Validates .env file existence

#### 8. `/cleanup.sh`
- **Complete cleanup**: Includes storage and secrets cleanup
- **Safe deletion**: Uses `--ignore-not-found=true` flags

#### 9. `/K8S_README.md`
- **Updated documentation**: Reflects new secrets and configmaps approach
- **Environment variable separation**: Documents sensitive vs non-sensitive variables

## 🔐 **Environment Variable Mapping**

### Secrets (Sensitive Data)
```yaml
AWS_ACCESS_KEY_ID      → app-secrets
AWS_SECRET_ACCESS_KEY  → app-secrets  
GITHUB_TOKEN          → app-secrets
```

### ConfigMaps (Non-Sensitive Data)
```yaml
BEDROCK_REGION                → app-config
BEDROCK_COMPLETION_MODEL_ID   → app-config
BEDROCK_EMBEDDING_MODEL_ID    → app-config
CHROMA_PERSIST_DIR            → app-config
DATABASE_URL                  → app-config
DEBUG                         → app-config
```

## 🚀 **Deployment Flow**

1. **Validate environment**: Check for `.env` file
2. **Create secrets**: `kubectl create secret generic app-secrets --from-env-file=.env`
3. **Build images**: Docker build for backend and frontend
4. **Apply manifests**: Storage → ConfigMaps → Deployments → Services
5. **Wait for readiness**: Health checks ensure pods are ready

## 🔄 **Development vs Production**

### Development Mode
- Uses `.env` file via `dotenv`
- Direct API calls to backend
- CORS allows localhost origins

### Production Mode (Kubernetes)
- Uses environment variables from secrets/configmaps
- nginx reverse proxy handles API routing
- Health checks ensure service availability
- Persistent storage for data

## 🛡️ **Security Improvements**

✅ **No secrets in Git**: All sensitive data stays in `.env` (gitignored)  
✅ **Runtime secret creation**: Secrets created from .env during deployment  
✅ **Separation of concerns**: Sensitive vs non-sensitive data properly separated  
✅ **Kubernetes-native**: Uses standard Kubernetes secrets and configmaps  
✅ **Environment detection**: Automatically adapts to runtime environment  

## 📊 **File Structure**

```
k8s/
├── app-configmap.yaml      # Non-sensitive configuration
├── backend.yaml            # Backend deployment + service
├── configmap.yaml          # nginx configuration  
├── frontend.yaml           # Frontend deployment + service
└── storage.yaml            # Persistent volume claims

scripts/
├── deploy.sh               # Build and deploy everything
└── cleanup.sh              # Clean up all resources
```

## 🔧 **Usage**

```bash
# Deploy everything (creates secrets from .env automatically)
./deploy.sh

# Check status
kubectl get pods,services,pvc

# Access application
http://<node-ip>:30080

# Clean up
./cleanup.sh
```

Your application now properly uses Kubernetes secrets and configmaps while maintaining compatibility with local development using .env files!
