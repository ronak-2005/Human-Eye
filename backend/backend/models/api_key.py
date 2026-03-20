import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class APIKey(Base):
    __tablename__ = "api_keys"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash     = Column(String(255), nullable=False)
    name         = Column(String(100), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at   = Column(DateTime, nullable=True)
    user          = relationship("User",         back_populates="api_keys")
    verifications = relationship("Verification", back_populates="api_key")
