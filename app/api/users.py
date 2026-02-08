from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.database import get_db, SessionLocal
from app.models.user import User
from app.models.scraping_job import ScrapingJob
from app.models.notification import Notification
from app.services.openai_service import openai_service
from app.services.user_scraper import user_scraper_service
from app.utils.auth import get_current_user
from passlib.context import CryptContext

router = APIRouter(prefix="/api/users", tags=["users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserPreferencesUpdate(BaseModel):
    """Request model for updating user preferences"""
    topics: List[str]
    keywords: List[str]
    source: str = "both"
    frequency: str = "daily"
    summaryLength: str = "concise"
    autoScrape: bool = False  # NEW: Allow frontend to control auto-scraping
    deliveryTime: str = "08:00"  # Default 8:00 AM
    deliveryDay: Optional[str] = "monday"  # For weekly frequency
    deliveryDate: Optional[int] = 1  # For monthly frequency (1-28)
    timezone: str = "UTC"  # User's timezone


class UserCreate(BaseModel):
    """Request model for creating a user"""
    email: EmailStr
    preferences: dict = {}


class UserProfileUpdate(BaseModel):
    """Request model for updating user profile"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserPasswordChange(BaseModel):
    """Request model for changing password"""
    current_password: str
    new_password: str


def start_scraping_job_for_user(user_id: int, job_id: int):
    """Background task to start scraping after preferences are saved"""
    db = SessionLocal()
    try:
        user_scraper_service.scrape_for_user_with_tracking(
            db=db,
            user_id=user_id,
            job_id=job_id,
            max_articles_per_source=10
        )

        # After scraping completes successfully, create success notification
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job and job.status == 'completed':
            notification = Notification(
                user_id=user_id,
                title="✅ Scraping Complete",
                message=f"Found {job.articles_saved} new articles! View them on your Dashboard.",
                type="success",
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.add(notification)
            db.commit()

    except Exception as e:
        print(f"Error in auto-scraping for user {user_id}: {e}")
    finally:
        db.close()


@router.post("/preferences")
async def update_user_preferences(
    user_id: int,
    preferences: UserPreferencesUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Update user preferences and generate preference embedding

    This endpoint:
    1. Updates user preferences in the database
    2. Generates a vector embedding from topics and keywords
    3. Stores the embedding for future personalized retrieval
    4. Automatically starts background scraping to fetch articles
    """
    try:
        # Find user
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update preferences
        user.preferences = preferences.dict()

        # Generate preference embedding
        preference_embedding = openai_service.generate_user_preference_embedding(
            topics=preferences.topics,
            keywords=preferences.keywords
        )

        user.preferences_embedding = preference_embedding

        db.commit()
        db.refresh(user)

        # Auto-scrape when user has topics (always enabled for fresh content)
        scraping_job = None
        if preferences.topics and len(preferences.topics) > 0:
            # Check if there's already a running job
            existing_job = db.query(ScrapingJob).filter(
                ScrapingJob.user_id == user_id,
                ScrapingJob.status.in_(["pending", "running"])
            ).first()

            if not existing_job:
                # Create new scraping job
                scraping_job = ScrapingJob(
                    user_id=user_id,
                    status="pending",
                    current_step="queued",
                    message="Finding articles based on your new preferences..."
                )
                db.add(scraping_job)
                db.commit()
                db.refresh(scraping_job)

                # Create notification for preference-triggered scraping
                notification = Notification(
                    user_id=user_id,
                    title="🔄 Scraping Started",
                    message=f"Finding articles based on your updated preferences: {', '.join(preferences.topics[:3])}...",
                    type="info",
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.add(notification)
                db.commit()

                # Start background scraping
                background_tasks.add_task(
                    start_scraping_job_for_user,
                    user_id=user_id,
                    job_id=scraping_job.id
                )
                print(f"[Preferences] Auto-scraping triggered for user {user.email} (job {scraping_job.id})")
            else:
                print(f"[Preferences] Skipping auto-scrape for user {user.email}, job {existing_job.id} already active")

        return {
            "success": True,
            "message": "Preferences updated successfully",
            "embedding_updated": True,
            "auto_scraping_started": scraping_job is not None,
            "scraping_job_id": scraping_job.id if scraping_job else None,
            "user": user.to_dict()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating preferences: {str(e)}")


@router.post("/")
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Create new user
        new_user = User(
            email=user_data.email,
            preferences=user_data.preferences
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "success": True,
            "message": "User created successfully",
            "user": new_user.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.to_dict()


@router.get("/email/{email}")
async def get_user_by_email(
    email: str,
    db: Session = Depends(get_db)
):
    """Get user by email"""
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.to_dict()


@router.get("/me/profile")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    # Derive name from email (username part before @)
    name = current_user.email.split('@')[0] if current_user.email else "User"

    return {
        "id": current_user.id,
        "name": name,
        "email": current_user.email,
        "role": current_user.role,
        "status": "Active" if current_user.is_active else "Inactive",
        "created_at": current_user.created_at.isoformat() if hasattr(current_user, 'created_at') and current_user.created_at else None,
        "preferences": current_user.preferences
    }


@router.put("/me/profile")
async def update_my_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    try:
        # Note: User model doesn't have a 'name' field, so we ignore it
        # Name is derived from email on the frontend

        # Update email if provided and not already taken
        if profile_data.email is not None and profile_data.email != current_user.email:
            # Check if email is already in use
            existing_user = db.query(User).filter(
                User.email == profile_data.email,
                User.id != current_user.id
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="Email is already in use by another account"
                )

            current_user.email = profile_data.email

        db.commit()
        db.refresh(current_user)

        # Derive name from email
        name = current_user.email.split('@')[0] if current_user.email else "User"

        return {
            "success": True,
            "message": "Profile updated successfully",
            "user": {
                "id": current_user.id,
                "name": name,
                "email": current_user.email,
                "role": current_user.role
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")


@router.post("/me/change-password")
async def change_my_password(
    password_data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    try:
        # Verify current password FIRST
        if not pwd_context.verify(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )

        # Validate new password length BEFORE hashing
        if len(password_data.new_password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters long"
            )

        if len(password_data.new_password) > 72:
            raise HTTPException(
                status_code=400,
                detail="Password is too long. Please use a password with 72 characters or less."
            )

        # Hash new password
        new_hashed_password = pwd_context.hash(password_data.new_password)
        current_user.hashed_password = new_hashed_password

        db.commit()

        return {
            "success": True,
            "message": "Password changed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error changing password: {str(e)}")
