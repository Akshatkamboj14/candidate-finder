from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.sql import func
from .database import Base


class Candidate(Base):
    __tablename__ = "candidates"


    id = Column(String, primary_key=True, index=True)
    source = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    profile_text = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


    def to_dict(self):
        return {
                "id": self.id,
                "source": self.source,
                "filename": self.filename,
                "profile_text": self.profile_text,
                "metadata": self.metadata,
                "created_at": self.created_at.isoformat() if self.created_at else None,
            }