from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from typing import List
from app.database import Base
import enum


class SourceType(enum.Enum):
    """Source type enum"""
    academic = "academic"
    financial = "financial"
    industry = "industry"


class RSSFeed(Base):
    """RSS Feed model for managing news sources"""
    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=False, unique=True)
    source_type = Column(Enum(SourceType), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<RSSFeed(name='{self.name}', type='{self.source_type.value}')>"

    @classmethod
    def get_active_feeds_by_type(cls, db: Session, source_type: str) -> List['RSSFeed']:
        """Get all active RSS feeds for a specific source type"""
        return db.query(cls).filter(
            cls.is_active == True,
            cls.source_type == source_type
        ).all()

    @classmethod
    def get_all_active_feeds(cls, db: Session) -> List['RSSFeed']:
        """Get all active RSS feeds"""
        return db.query(cls).filter(cls.is_active == True).all()

    def to_dict(self):
        """Convert to dictionary for easy use"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "source_type": self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
