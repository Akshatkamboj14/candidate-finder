from sqlalchemy.future import select
from sqlalchemy import insert
from .models import Candidate
from sqlalchemy.ext.asyncio import AsyncSession


async def create_candidate(db: AsyncSession, candidate_dict: dict):
    """Insert a new candidate row and return the Candidate object."""
    obj = Candidate(
    id=candidate_dict.get("id"),
    source=candidate_dict.get("source"),
    filename=candidate_dict.get("filename"),
    profile_text=candidate_dict.get("profile_text"),
    metadata=candidate_dict.get("metadata", {}),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_candidate(db: AsyncSession, candidate_id: str):
    q = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    return q.scalars().first()


async def list_candidates(db: AsyncSession, limit: int = 100):
    q = await db.execute(select(Candidate).limit(limit))
    return q.scalars().all()