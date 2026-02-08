"""Admin authentication and authorization utilities"""

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.user import User
from app.api.auth import get_current_user
from app.database import get_db


async def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to require admin role for protected endpoints.

    Usage:
        @router.get("/admin/users")
        async def get_all_users(admin: User = Depends(require_admin)):
            ...
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )

    return current_user
