import time
import uuid
from typing import Dict, Any
from fastapi import BackgroundTasks
from ..features.github.github_connector_async import GitHubConnectorAsync
from ..infrastructure.aws.vectorstore import collection, clear_collection
import json

class GitHubService:
    def __init__(self):
        self.ingest_jobs: Dict[str, Dict[str, Any]] = {}
        self.github = GitHubConnectorAsync()
        
    async def clear_database(self) -> dict:
        """Clear all data from the collection"""
        try:            
            if not collection:
                return {"success": False, "error": "Database collection is not initialized"}
                
            if clear_collection():
                try:
                    result = collection.get()
                    if not result or not result.get("ids"):
                        return {"success": True, "message": "Database cleared successfully"}
                    else:
                        return {"success": False, "error": "Failed to verify database was cleared"}
                except Exception as e:
                    return {"success": False, "error": f"Error verifying database clear: {str(e)}"}
            else:
                return {"success": False, "error": "Failed to clear database"}
        except Exception as e:
            return {"success": False, "error": f"Database clear error: {str(e)}"}

    async def start_fetch_job(
        self, 
        language: str | None, 
        location: str | None,
        min_followers: int | None, 
        min_repos: int | None,
        max_users: int, 
        per_user_repos: int, 
        background_tasks: BackgroundTasks
    ) -> dict:
        """Start a background job to fetch GitHub users"""
        query_parts = ["type:user"]
        
        if language:
            query_parts.append(f"language:{language}")
            
        if location:
            location_clean = location.strip().lower()
            query_parts.append(f"location:*{location_clean}*")
            
        if min_followers:
            query_parts.append(f"followers:>={min_followers}")
            
        if min_repos:
            query_parts.append(f"repos:>={min_repos}")
            
        query_parts.append("sort:followers")
        
        query = " ".join(query_parts)
            
        job_id = str(uuid.uuid4())
        self.ingest_jobs[job_id] = {
            "status": "pending",
            "started_at": time.time(),
            "result": None
        }

        background_tasks.add_task(
            self._run_fetch_job,
            job_id,
            query,
            max_users,
            per_user_repos
        )

        return {"job_id": job_id, "status": "started"}

    def get_job_status(self, job_id: str) -> dict:
        """Get the status of a GitHub fetch job"""
        return self.ingest_jobs.get(job_id, {"error": "job not found"})

    async def inspect_collection(self) -> dict:
        """Get an overview of the vector collection"""
        try:
            result = collection.get(
                include=["documents", "metadatas"]
            )
            
            if not isinstance(result, dict):
                return {"error": "Invalid collection response"}
                
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            
            min_len = min(len(ids), len(docs), len(metas))
            
            out = [
                {
                    "id": ids[i],
                    "doc_preview": (docs[i][:200] if docs[i] else "") if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {}
                }
                for i in range(min_len)
            ]
            
            return {
                "count": len(out),
                "items": out
            }
        except Exception as e:
            return {"error": str(e)}

    async def filter_by_skill(self, skill: str, max_results: int = 100) -> dict:
        """Filter candidates by a specific skill"""
        try:
            out = []
            skill_lower = (skill or "").strip().lower()
            if not skill_lower:
                return {"count": 0, "items": []}

            p = collection.peek()
            ids = p.get("ids", [])
            docs = p.get("documents", [])
            metas = p.get("metadatas", [])

            for i, id_ in enumerate(ids):
                if len(out) >= max_results:
                    break
                
                meta = metas[i] if i < len(metas) else {}
                doc_text = docs[i] if i < len(docs) else ""
                
                if self._check_skill_match(skill_lower, meta, doc_text):
                    out.append({
                        "id": id_,
                        "doc_preview": (doc_text[:300] if doc_text else ""),
                        "metadata": meta
                    })

            return {"count": len(out), "items": out}
        except Exception as e:
            return {"error": str(e)}

    def _run_fetch_job(self, job_id: str, query: str, max_users: int, per_user_repos: int) -> None:
        """Execute the GitHub fetch job"""
        try:
            res = self.github.fetch_and_index_github_users_concurrent(
                query=query,
                max_users=max_users,
                per_user_repos=per_user_repos,
                concurrency=8
            )
            self.ingest_jobs[job_id].update({
                "status": "done",
                "result": res,
                "finished_at": time.time()
            })
        except Exception as e:
            self.ingest_jobs[job_id].update({
                "status": "failed",
                "result": {"error": str(e)}
            })

    def _check_skill_match(self, skill_lower: str, meta: dict, doc_text: str) -> bool:
        """Check if a skill matches in metadata or document text"""
        skills_list_val = meta.get("skills_list") or meta.get("skills_list_json")
        if skills_list_val:
            try:
                parsed = (
                    json.loads(skills_list_val)
                    if isinstance(skills_list_val, str)
                    else skills_list_val
                )
                if isinstance(parsed, (list, tuple)):
                    if any(
                        isinstance(s, str) and skill_lower == s.strip().lower()
                        for s in parsed
                    ):
                        return True
            except Exception:
                if isinstance(skills_list_val, str):
                    if any(
                        skill_lower == s.strip().lower()
                        for s in skills_list_val.split(",")
                        if s.strip()
                    ):
                        return True

        skills_evidence_val = meta.get("skills_evidence_json") or meta.get("skills_evidence")
        if skills_evidence_val:
            try:
                evid = (
                    json.loads(skills_evidence_val)
                    if isinstance(skills_evidence_val, str)
                    else skills_evidence_val
                )
                if isinstance(evid, dict):
                    if any(
                        isinstance(k, str) and skill_lower == k.strip().lower()
                        for k in evid.keys()
                    ):
                        return True
            except Exception:
                pass

        return bool(doc_text and skill_lower in doc_text.lower())
