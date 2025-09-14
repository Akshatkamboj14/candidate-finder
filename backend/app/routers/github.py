from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from ..services.github_service import GitHubService

router = APIRouter()
github_service = GitHubService()

class GitHubFetchRequest(BaseModel):
    language: str | None = None
    location: str | None = None
    min_followers: int | None = None
    min_repos: int | None = None
    max_users: int = 30
    per_user_repos: int = 3

@router.post("/fetch_github_bg")
async def fetch_github_bg(req: GitHubFetchRequest, background_tasks: BackgroundTasks):
    """Start background GitHub user fetching process"""
    return await github_service.start_fetch_job(
        language=req.language,
        location=req.location,
        min_followers=req.min_followers,
        min_repos=req.min_repos,
        max_users=req.max_users,
        per_user_repos=req.per_user_repos,
        background_tasks=background_tasks
    )

@router.get("/fetch_github_job/{job_id}")
async def fetch_github_job(job_id: str):
    """Get status of a GitHub fetch job"""
    return github_service.get_job_status(job_id)

@router.get("/collection")
async def inspect_collection():
    """Get overview of the vector collection"""
    return await github_service.inspect_collection()

@router.get("/filter_by_skill")
async def filter_by_skill(skill: str, max_results: int = 100):
    """Filter candidates by specific skill"""
    return await github_service.filter_by_skill(skill, max_results)

@router.post("/clear_database")
async def clear_database():
    """Clear all data from the collection"""
    return await github_service.clear_database()