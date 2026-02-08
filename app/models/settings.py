from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SystemSettings(Base):
    """System settings for admin configuration"""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Convert settings to dictionary"""
        return {
            "key": self.key,
            "value": self.value,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }
