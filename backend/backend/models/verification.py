import uuid, enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class VerificationStatus(str, enum.Enum):
    PENDING     = "pending"
    COMPLETE    = "complete"
    FAILED      = "failed"
    UNAVAILABLE = "unavailable"

class Verification(Base):
    __tablename__ = "verifications"
    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id         = Column(String(255), nullable=False, index=True)
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    api_key_id         = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    human_trust_score  = Column(Integer, nullable=True)
    combined_score     = Column(String(10), nullable=True)
    behavioral_score   = Column(String(10), nullable=True)
    text_score         = Column(String(10), nullable=True)
    liveness_score     = Column(String(10), nullable=True)
    deepfake_probability = Column(String(10), nullable=True)
    clone_probability  = Column(String(10), nullable=True)
    verdict            = Column(String(50), nullable=True)
    confidence         = Column(String(20), nullable=True)
    flags              = Column(JSON, default=list)
    signals_analyzed   = Column(JSON, default=list)
    action_type        = Column(String(100), nullable=True)
    platform_user_id   = Column(String(255), nullable=True)
    ip_address         = Column(String(45), nullable=True)
    user_agent         = Column(Text, nullable=True)
    status             = Column(String(20), default="pending", nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at       = Column(DateTime, nullable=True)
    user               = relationship("User",   back_populates="verifications")
    api_key            = relationship("APIKey", back_populates="verifications")
    webhook_deliveries = relationship("WebhookDelivery", back_populates="verification")
