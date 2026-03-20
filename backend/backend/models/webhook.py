import uuid, enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class WebhookStatus(str, enum.Enum):
    PENDING   = "pending"
    DELIVERED = "delivered"
    FAILED    = "failed"

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    url        = Column(String(2048), nullable=False)
    secret     = Column(String(255), nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user       = relationship("User",            back_populates="webhooks")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")

class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id     = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"))
    verification_id = Column(UUID(as_uuid=True), ForeignKey("verifications.id"))
    status          = Column(String(20), default="pending")
    response_code   = Column(Integer, nullable=True)
    attempt_count   = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    endpoint        = relationship("WebhookEndpoint", back_populates="deliveries")
    verification    = relationship("Verification",    back_populates="webhook_deliveries")
