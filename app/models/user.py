from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base


class User(Base):
    """User model with preference embeddings for personalization"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Authentication fields
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    role = Column(String(20), default='user', nullable=False)  # 'user' or 'admin'

    # User preferences stored as JSON
    preferences = Column(JSON, default={})
    # {
    #   "topics": ["AI", "Machine Learning"],
    #   "keywords": ["transformers", "NLP"],
    #   "source": "academic",  # or "industry", "financial", "both"
    #   "frequency": "daily",
    #   "summaryLength": "concise"
    # }

    # Vector embedding of user preferences for semantic matching (1536-d for text-embedding-3-large)
    preferences_embedding = Column(Vector(1536))

    # Set every time topics/keywords change. The ranking cache treats anything
    # older than this as stale, so new preferences take effect immediately.
    preferences_updated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

    def to_dict(self):
        """Convert user to dictionary for API responses (excludes password)"""
        return {
            "id": self.id,
            "email": self.email,
            "isActive": self.is_active,
            "isVerified": self.is_verified,
            "role": self.role,
            "preferences": self.preferences or {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }
