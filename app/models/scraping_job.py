"""
Scraping Job Model

Tracks background scraping jobs for users, allowing the frontend
to poll for status and show progress updates.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ScrapingJob(Base):
    """Model for tracking background scraping jobs"""

    __tablename__ = "scraping_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Job status: pending, running, completed, failed
    status = Column(String(50), nullable=False, default="pending", index=True)

    # Current step: initializing, fetching, processing, generating_embeddings, saving, completed
    current_step = Column(String(100), default="initializing")

    # User-friendly message
    message = Column(String(500), default="Getting ready to find your articles...")

    # Progress tracking
    total_articles_found = Column(Integer, default=0)
    articles_processed = Column(Integer, default=0)
    articles_saved = Column(Integer, default=0)

    # Source breakdown
    source_stats = Column(JSON, default={})
    # {
    #   "academic": 5,
    #   "industry": 3,
    #   "financial": 2
    # }

    # Error information (if failed)
    error_message = Column(String(1000), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ScrapingJob(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

    def to_dict(self):
        """Convert job to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "current_step": self.current_step,
            "message": self.message,
            "progress": {
                "total_found": self.total_articles_found,
                "processed": self.articles_processed,
                "saved": self.articles_saved,
            },
            "source_stats": self.source_stats or {},
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
