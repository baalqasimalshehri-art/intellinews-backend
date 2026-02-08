from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from app.database import Base
import secrets


class PasswordResetToken(Base):
    """Password reset token model"""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used})>"

    def is_valid(self) -> bool:
        """Check if token is still valid (not used and not expired)"""
        return not self.used and datetime.utcnow() < self.expires_at

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def calculate_expiry(hours: int = 1) -> datetime:
        """Calculate expiry time from now"""
        return datetime.utcnow() + timedelta(hours=hours)

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "used": self.used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
