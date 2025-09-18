from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
from ..features.k8s.k8s_assistant import K8sAssistant

router = APIRouter()
k8s_assistant = K8sAssistant()

class K8sQuery(BaseModel):
    query: str

@router.post("/query")
async def process_k8s_query(query: K8sQuery) -> Dict[str, Any]:
    """
    Process a natural language query about Kubernetes resources.
    
    Examples:
    - "list all pods"
    - "show logs for pod frontend-xyz"
    - "describe service backend"
    - "get deployments in namespace production"
    """
    try:
        result = await k8s_assistant.process_query(query.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint for K8s assistant"""
    return {"status": "healthy", "service": "k8s-assistant"}
