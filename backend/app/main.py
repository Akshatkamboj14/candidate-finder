import os
from dotenv import load_dotenv

# Load environment variables FIRST, before any other imports
def load_environment():
    try:
        # In Kubernetes, environment variables are provided by secrets/configmaps
        # Check if we're running in Kubernetes (no .env file needed)
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            print("[INFO] Running in Kubernetes - using environment variables from secrets/configmaps")
            return
        
        # Development mode - load from .env file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
        
        # Print key paths for debugging
        print(f"[DEBUG] Current directory: {current_dir}")
        print(f"[DEBUG] Project root: {root_dir}")
        
        # Look for .env file in project root
        env_path = os.path.join(root_dir, '.env')
        print(f"[DEBUG] Looking for .env at: {env_path}")
        
        if os.path.exists(env_path):
            print(f"[DEBUG] Found .env file at: {env_path}")
            
            # Load environment variables
            print("[DEBUG] Loading environment variables...")
            load_dotenv(env_path, override=True)
            
        else:
            print(f"[DEBUG] No .env file found at: {env_path}")
            print("[INFO] Running without .env file - using system environment variables")
            
        # Print loaded environment variables (without values for security)
        print("[DEBUG] Environment variables status:")
        print(f"[DEBUG] BEDROCK_REGION = {os.getenv('BEDROCK_REGION', 'Not Set')}")
        print(f"[DEBUG] BEDROCK_COMPLETION_MODEL_ID = {os.getenv('BEDROCK_COMPLETION_MODEL_ID', 'Not Set')}")
        print(f"[DEBUG] BEDROCK_EMBEDDING_MODEL_ID = {os.getenv('BEDROCK_EMBEDDING_MODEL_ID', 'Not Set')}")
        print(f"[DEBUG] AWS_ACCESS_KEY_ID = {'Set' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not Set'}")
        print(f"[DEBUG] AWS_SECRET_ACCESS_KEY = {'Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'Not Set'}")
        print(f"[DEBUG] GITHUB_TOKEN = {'Set' if os.getenv('GITHUB_TOKEN') else 'Not Set'}")
        print(f"[DEBUG] DATABASE_URL = {'Set' if os.getenv('DATABASE_URL') else 'Not Set'}")
        print(f"[DEBUG] CHROMA_PERSIST_DIR = {os.getenv('CHROMA_PERSIST_DIR', 'Not Set')}")
        
        # Export AWS region to AWS_DEFAULT_REGION if not set
        if not os.getenv('AWS_DEFAULT_REGION') and os.getenv('BEDROCK_REGION'):
            os.environ['AWS_DEFAULT_REGION'] = os.getenv('BEDROCK_REGION')
            print(f"[DEBUG] Set AWS_DEFAULT_REGION to {os.getenv('BEDROCK_REGION')}")
            
    except Exception as e:
        print(f"[ERROR] Error in load_environment: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Don't raise in production - continue with system environment variables

# Load environment before anything else
load_environment()

# Now we can import the rest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .routers import jobs, github, k8s
from .core.database.database import init_db

# Create FastAPI app
app = FastAPI(title="JD → Candidates")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the database when the application starts"""
    try:
        await init_db()
        print("[INFO] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        # Don't raise - let app start but log the error

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development React app
        "http://54.166.229.126:3000",  # Your specific URL
        "*"  # Allow all origins for NodePort service in Kubernetes
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static frontend files - DISABLED for Kubernetes deployment with separate frontend
# frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
# app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="frontend")

# Final environment check before including routers
print("[DEBUG] Final Environment Check:")
print(f"[DEBUG] AWS_ACCESS_KEY_ID: {'Set' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not Set'}")
print(f"[DEBUG] AWS_SECRET_ACCESS_KEY: {'Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'Not Set'}")
print(f"[DEBUG] AWS_DEFAULT_REGION: {os.getenv('AWS_DEFAULT_REGION', 'Not Set')}")
print(f"[DEBUG] BEDROCK_REGION: {os.getenv('BEDROCK_REGION', 'Not Set')}")

# Include routers
app.include_router(jobs.router, prefix="/api")
app.include_router(github.router, prefix="/api")
app.include_router(k8s.router, prefix="/api/k8s", tags=["k8s"])

# Health check endpoint for Kubernetes
@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes liveness and readiness probes"""
    return {
        "status": "healthy",
        "environment": {
            "aws_configured": bool(os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')),
            "bedrock_region": os.getenv('BEDROCK_REGION', 'not_set'),
            "github_token": bool(os.getenv('GITHUB_TOKEN')),
            "database_url": bool(os.getenv('DATABASE_URL')),
            "chroma_persist_dir": os.getenv('CHROMA_PERSIST_DIR', 'not_set')
        }
    }




