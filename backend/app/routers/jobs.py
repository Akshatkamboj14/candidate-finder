from fastapi import APIRouter, BackgroundTasks, HTTPException, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ..services.job_service import JobService
from ..services.rag_service import RAGService

router = APIRouter()
job_service = JobService()
rag_service = RAGService()

class JobRequest(BaseModel):
    jd: str
    k: int = 10

@router.post("/job")
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    """Create a job: embed JD, query vector DB for top-k candidates"""
    try:
        if not req.jd.strip():
            raise HTTPException(status_code=400, detail="Job description cannot be empty")
        return await job_service.create_job(req.jd, req.k)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in create_job: {str(e)}")  # Debug logging
        raise HTTPException(status_code=500, detail=f"job_creation_failed: {str(e)}")

@router.post("/rag")
async def rag_answer(job_id: Optional[str] = Form(None), query: str = Form(...), jd: Optional[str] = Form(None)):
    """Perform RAG query on job documents"""
    try:
        return await rag_service.process_rag_query(job_id, query, jd)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag_failed: {str(e)}")