from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class NewsletterLog(Base):
    """Newsletter dispatch log for admin tracking"""

    __tablename__ = "newsletter_logs"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(500), nullable=False)
    recipients = Column(Integer, default=0)
    status = Column(String(50), default='Completed')  # 'Completed', 'Failed', 'In Progress'
    created_at = Column(DateTime, server_default=func.now())
    # Per-user tracking: nullable so existing rows aren't broken
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    def to_dict(self):
        """Convert newsletter log to dictionary"""
        return {
            "id": self.id,
            "subject": self.subject,
            "recipients": self.recipients,
            "status": self.status,
            "date": self.created_at.strftime('%B %d, %Y') if self.created_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }
