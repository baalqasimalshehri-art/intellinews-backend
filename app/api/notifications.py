from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.notification import Notification
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    """Request model for creating a notification"""
    title: str
    message: str
    notification_type: str = "info"
    link: str | None = None


@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_dismissed: bool = False
):
    """
    Get all notifications for the current user

    Returns notifications ordered by creation date (newest first)
    """
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if not include_dismissed:
        query = query.filter(Notification.dismissed == False)

    notifications = query.order_by(desc(Notification.created_at)).all()

    return {
        "notifications": [n.to_dict() for n in notifications],
        "unreadCount": sum(1 for n in notifications if not n.read and not n.dismissed)
    }


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
        Notification.dismissed == False
    ).count()

    return {"unreadCount": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.read = True
    notification.read_at = datetime.utcnow()
    db.commit()

    return {"success": True, "notification": notification.to_dict()}


@router.post("/{notification_id}/unread")
async def mark_as_unread(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as unread"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.read = False
    notification.read_at = None
    db.commit()

    return {"success": True, "notification": notification.to_dict()}


@router.post("/mark-all-read")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False
    ).update({
        "read": True,
        "read_at": datetime.utcnow()
    })
    db.commit()

    return {"success": True, "message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def dismiss_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss (soft delete) a notification"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.dismissed = True
    db.commit()

    return {"success": True, "message": "Notification dismissed"}


@router.post("/")
async def create_notification(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new notification for the current user

    This is mainly for testing purposes. In production, notifications
    would be created by system events (article updates, newsletter sent, etc.)
    """
    new_notification = Notification(
        user_id=current_user.id,
        title=notification_data.title,
        message=notification_data.message,
        notification_type=notification_data.notification_type,
        link=notification_data.link
    )

    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)

    return {
        "success": True,
        "notification": new_notification.to_dict()
    }
