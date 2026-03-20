import uuid
from datetime import datetime
from sqlalchemy import Column, Float, Integer, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

class Score(Base):
    __tablename__ = "scores"
    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform_user_id   = Column(String(255), nullable=False, index=True)
    current_score      = Column(Float, nullable=False, default=50.0)
    verification_count = Column(Integer, default=0)
    last_verified_at   = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
