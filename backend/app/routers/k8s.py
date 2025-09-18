from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
from ..features.k8s.k8s_langgraph_assistant import K8sLangGraphAssistant

router = APIRouter()
k8s_assistant = K8sLangGraphAssistant()

class K8sQuery(BaseModel):
    query: str

@router.post("/query")
async def process_k8s_query(query: K8sQuery) -> Dict[str, Any]:
    """
    Process a natural language query about Kubernetes resources using LangGraph workflow.
    
    The LangGraph workflow includes:
    1. Security validation and access control
    2. Intent parsing with LLM and fallback
    3. Resource name resolution
    4. Kubectl command execution
    5. AI-enhanced response generation
    
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
