from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    """Notification model for user alerts"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Notification content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="info")  # info, success, warning, error, system

    # Status
    read = Column(Boolean, default=False, index=True)
    dismissed = Column(Boolean, default=False)

    # Metadata
    link = Column(String(500), nullable=True)  # Optional link for the notification

    created_at = Column(DateTime, server_default=func.now(), index=True)
    read_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, title='{self.title}')>"

    def to_dict(self):
        """Convert notification to dictionary for API responses"""
        from datetime import datetime, timezone

        # Calculate relative time
        time_str = self._get_relative_time()

        return {
            "id": str(self.id),
            "title": self.title,
            "message": self.message,
            "type": self.notification_type,
            "read": self.read,
            "time": time_str,
            "link": self.link,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "readAt": self.read_at.isoformat() if self.read_at else None
        }

    def _get_relative_time(self):
        """Get relative time string like '2M AGO', '1H AGO'"""
        if not self.created_at:
            return "NOW"

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        created = self.created_at.replace(tzinfo=timezone.utc) if self.created_at.tzinfo is None else self.created_at
        diff = now - created

        seconds = diff.total_seconds()

        if seconds < 60:
            return "JUST NOW"
        elif seconds < 3600:  # Less than an hour
            minutes = int(seconds / 60)
            return f"{minutes}M AGO"
        elif seconds < 86400:  # Less than a day
            hours = int(seconds / 3600)
            return f"{hours}H AGO"
        else:
            days = int(seconds / 86400)
            return f"{days}D AGO"
