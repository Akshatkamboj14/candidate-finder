import uuid
import os
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from .utils.parser import parse_pdf_bytes
from .utils.embeddings import get_embedding_for_text, get_text_completion
from .utils.vectorstore import upsert_profile, query_similar
from dotenv import load_dotenv

load_dotenv()


app = FastAPI(title="JD → Candidates (Phase 1)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple in-memory job store for demo
JOB_STORE = {}


class JobRequest(BaseModel):
    jd: str
    k: int = 10


@app.post("/api/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume (PDF) — parse, embed, and index into Chroma"""
    contents = await file.read()
    text = parse_pdf_bytes(contents)
    profile_id = str(uuid.uuid4())
    profile = {
        "id": profile_id,
        "source": "upload",
        "filename": file.filename,
        "profile_text": text,
    }
    # embed & upsert
    vec = get_embedding_for_text(text)
    upsert_profile(
        profile_id, text, vec, metadata={"source": "upload", "filename": file.filename}
    )
    return {"status": "ok", "id": profile_id}


@app.post("/api/job")
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    jd = req.jd
    k = req.k
    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {"jd": jd, "k": k}

    # embed JD
    jd_vec = get_embedding_for_text(jd)

    # query vector DB
    results = query_similar(jd_vec, k=k)

    # return immediate results (profiles already indexed will appear).
    return {"job_id": job_id, "results": results}


@app.post("/api/rag")
async def rag_answer(job_id: str = Form(...), query: str = Form(...)):
    """Simple RAG: retrieve top docs for the job and call LLM for answer."""
    job = JOB_STORE.get(job_id)
    if not job:
        return {"error": "job not found"}
    jd = job["jd"]
    # retrieve top docs for the JD (we re-run a search using JD)
    jd_vec = get_embedding_for_text(jd)
    docs = query_similar(jd_vec, k=6)
    # build prompt
    context = "\n\n---\n\n".join([d["document"] for d in docs])
    prompt = f"You are an assistant. Use the following candidate contexts to answer the question.\n\nCONTEXT:\n{context}\n\nQUESTION:\n{query}\n\nAnswer concisely and list candidate ids you referenced."
    answer = get_text_completion(prompt)
    return {"answer": answer, "sources": [d["id"] for d in docs]}