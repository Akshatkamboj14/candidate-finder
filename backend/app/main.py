import uuid
import os
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from .utils.parser import parse_pdf_bytes
from .utils.embeddings import get_embedding_for_text, get_text_completion
from .utils.vectorstore import upsert_profile, query_similar
from dotenv import load_dotenv
# at top of main.py add import
import threading, time
from .utils.github_connector_async import fetch_and_index_github_users_concurrent
from fastapi import Response
from fastapi import Form, HTTPException
from .utils.skills import extract_keywords_from_jd, find_evidence_for_skills


INGEST_JOBS = {}




# load .env from project root, regardless of where uvicorn is run
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


if os.path.isfile(BASE_DIR):
    load_dotenv(BASE_DIR)
else:
    # fallback to default behavior (load from CWD)
    load_dotenv()






app = FastAPI(title="JD → Candidates (Phase 1)")

from fastapi.staticfiles import StaticFiles
import os
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="frontend")



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




from fastapi import HTTPException

@app.post("/api/job")
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    """
    Create a job: embed JD, query vector DB for top-k.
    Returns JSON with job_id and immediate results. Saves job in JOB_STORE (in-memory).
    Wrapped with try/except to always return JSON even on error.
    """
    try:
        jd = req.jd
        k = req.k
        job_id = str(uuid.uuid4())
        JOB_STORE[job_id] = {"jd": jd, "k": k}
        # embed JD
        jd_vec = get_embedding_for_text(jd)
        # query vector DB
        results = query_similar(jd_vec, k=k)
        return {"job_id": job_id, "results": results}
    except Exception as e:
        # log full traceback server-side and return a JSON error
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"job_creation_failed: {str(e)}")


@app.post("/api/rag")
async def rag_answer(job_id: str = Form(None), query: str = Form(...), jd: str = Form(None)):
    """
    Flexible RAG:
    - Accepts job_id OR jd parameter. If neither provided -> error.
    - Extracts skills from JD, finds evidence snippets in retrieved docs,
      builds a prompt including candidate contexts + evidence, and calls LLM.
    - Returns the model 'answer', list of source ids, and the evidence map per candidate.
    """
    try:
        # determine JD to use
        if job_id:
            job = JOB_STORE.get(job_id)
            if job:
                jd_text = job["jd"]
            else:
                if jd:
                    jd_text = jd
                else:
                    return {"error": "job not found; provide 'jd' parameter to run RAG without a stored job"}
        else:
            if jd:
                jd_text = jd
            else:
                return {"error": "must provide either job_id or jd"}

        # embed JD & retrieve top docs
        jd_vec = get_embedding_for_text(jd_text)
        docs = query_similar(jd_vec, k=6)

        # skill extraction from JD (general)
        skill_tokens = extract_keywords_from_jd(jd_text, top_k=8)

        # find evidence snippets for those tokens in docs
        evidence_map = find_evidence_for_skills(docs, skill_tokens)

        # Build context with evidence appended per candidate (keeps prompt informative)
        context_parts = []
        for d in docs:
            cid = d.get("id")
            doc_text = d.get("document","")
            evid = evidence_map.get(cid, [])
            ev_text = ""
            if evid:
                ev_text = "\nEvidence snippets:\n" + "\n".join([f"- {e}" for e in evid])
            context_parts.append(f"Candidate: {cid}\n{doc_text}\n{ev_text}")

        context = "\n\n---\n\n".join(context_parts)

        # Improved prompt template: ask to cite evidence and give confidence
        prompt = f"""
SYSTEM: You are an assistant that answers recruiter questions about candidates. Use ONLY the CONTEXT below — do NOT hallucinate.
INSTRUCTIONS:
1) For each candidate, say whether they match the query and list the exact evidence snippets you used (quotations).
2) Provide a confidence label for each candidate: HIGH / MEDIUM / LOW.
3) At the end, give a short conclusions list of candidate ids that match.

CONTEXT:
{context}

JD:
{jd_text}

QUERY:
{query}

Answer now.
"""

        answer = get_text_completion(prompt)
        # return answer, the candidate ids used as sources, and the evidence_map
        return {"answer": answer, "sources": [d.get("id") for d in docs], "evidence": evidence_map}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"rag_failed: {str(e)}")


# add model for request
class GitHubFetchRequest(BaseModel):
    query: str           # e.g., "language:python location:india followers:>10"
    max_users: int = 30
    per_user_repos: int = 3

# add endpoint

@app.post("/api/fetch_github_bg")
async def fetch_github_bg(req: GitHubFetchRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    INGEST_JOBS[job_id] = {"status": "pending", "started_at": time.time(), "result": None}

    def _run_job(job_id, query, max_users, per_user_repos):
        try:
            res = fetch_and_index_github_users_concurrent(query=query, max_users=max_users, per_user_repos=per_user_repos, concurrency=8)
            INGEST_JOBS[job_id]["status"] = "done"
            INGEST_JOBS[job_id]["result"] = res
            INGEST_JOBS[job_id]["finished_at"] = time.time()
        except Exception as e:
            INGEST_JOBS[job_id]["status"] = "failed"
            INGEST_JOBS[job_id]["result"] = {"error": str(e)}

    # run in background thread
    background_tasks.add_task(_run_job, job_id, req.query, req.max_users, req.per_user_repos)
    return {"job_id": job_id, "status": "started"}





@app.get("/api/fetch_github_job/{job_id}")
async def fetch_github_job(job_id: str):
    return INGEST_JOBS.get(job_id, {"error":"job not found"})



@app.get("/api/collection")
async def inspect_collection():
    """
    Return a lightweight view of the Chroma collection as seen by the running server.
    Safe for debugging — returns ids, first 200 chars of each doc, and metadata.
    """
    try:
        # 'collection' is imported in your vectorstore module
        from .utils import vectorstore
        col = vectorstore.collection
        # try peek if available
        try:
            p = col.peek()
            # normalize peek result to a small summary
            ids = p.get("ids", [])
            docs = p.get("documents", [])
            metas = p.get("metadatas", [])
            out = []
            for i, idx in enumerate(ids):
                out.append({
                    "id": idx,
                    "doc_preview": (docs[i][:200] if i < len(docs) and docs[i] else "") ,
                    "metadata": (metas[i] if i < len(metas) else {})
                })
            return {"count": len(ids), "items": out}
        except Exception:
            # fallback: try a small query (text query) to list some documents
            try:
                q = col.query(query_texts=["test"], n_results=20)
                # q can be dict with ids/documents
                ids = q.get("ids", [[]])[0]
                docs = q.get("documents", [[]])[0]
                metas = q.get("metadatas", [[]])[0]
                out = []
                for i, idx in enumerate(ids):
                    out.append({"id": idx, "doc_preview": (docs[i][:200] if i < len(docs) else ""), "metadata": metas[i] if i < len(metas) else {}})
                return {"count": len(ids), "items": out}
            except Exception as e:
                return Response(content=f"Could not inspect collection: {e}", status_code=500)
    except Exception as e:
        return Response(content=f"Inspect error: {e}", status_code=500)



@app.get("/api/filter_by_skill")
async def filter_by_skill(skill: str):
    """
    Return candidates flagged for a skill. For now supports 'pytorch' via metadata 'pyTorchEvidence'.
    This is a simple, fast debugging endpoint; you can expand it to general skill lists later.
    """
    try:
        from .utils import vectorstore
        col = vectorstore.collection
        # try peek (works in the server process)
        try:
            p = col.peek()
            ids = p.get("ids", [])
            docs = p.get("documents", [])
            metas = p.get("metadatas", [])
            out = []
            for i, id_ in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                has_skill = False
                if skill.lower() == "pytorch":
                    has_skill = meta.get("pyTorchEvidence", False)
                # fallback: check doc text for skill token
                if not has_skill and i < len(docs):
                    if skill.lower() in (docs[i] or "").lower():
                        has_skill = True
                if has_skill:
                    out.append({
                        "id": id_,
                        "doc_preview": (docs[i][:300] if i < len(docs) else ""),
                        "metadata": meta
                    })
            return {"count": len(out), "items": out}
        except Exception as e:
            return {"error": f"collection peek failed: {e}"}
    except Exception as exc:
        return {"error": str(exc)}



















