from typing import Optional

from pydantic import BaseModel


class CandidateOut(BaseModel):
    id: str
    source: Optional[str]
    filename: Optional[str]
    profile_text: str
    score: Optional[float]