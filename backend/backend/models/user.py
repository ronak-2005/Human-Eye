import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class User(Base):
    __tablename__ = "users"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email        = Column(String(255), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    plan         = Column(String(50), default="starter", nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    api_keys      = relationship("APIKey",          back_populates="user", cascade="all, delete-orphan")
    verifications = relationship("Verification",    back_populates="user")
    webhooks      = relationship("WebhookEndpoint", back_populates="user", cascade="all, delete-orphan")
