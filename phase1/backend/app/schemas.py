from pydantic import BaseModel
from typing import Optional, List


class CandidateOut(BaseModel):
    id: str
    source: Optional[str]
    filename: Optional[str]
    profile_text: str
    score: Optional[float]