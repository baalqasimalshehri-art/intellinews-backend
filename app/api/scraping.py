"""
API endpoints for article scraping

Allows users to trigger dynamic article scraping based on their preferences
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import threading
from app.database import get_db, SessionLocal
from app.utils.auth import get_current_user
from app.utils.admin import require_admin
from app.models.user import User
from app.models.scraping_job import ScrapingJob
from app.services.user_scraper import user_scraper_service


router = APIRouter(prefix="/api/scraping", tags=["scraping"])


class ScrapeRequest(BaseModel):
    """Request model for scraping articles"""
    max_articles_per_source: Optional[int] = 10


class ScrapeResponse(BaseModel):
    """Response model for scraping results"""
    success: bool
    message: str
    articles_scraped: int
    articles_saved: int
    by_source: dict
    topics: list
    keywords: list


@router.post("/scrape-for-me", response_model=ScrapeResponse)
async def scrape_for_current_user(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scrape articles based on the current user's preferences

    This endpoint:
    1. Gets the authenticated user's topics and keywords
    2. Scrapes academic, industry, and/or financial sources based on source preference
    3. Filters articles by relevance to user's interests
    4. Generates embeddings and AI summaries
    5. Saves unique articles to the database

    The scraping happens in the foreground to provide immediate feedback,
    but can be moved to background tasks if needed.
    """
    try:
        # Check if user has preferences set
        prefs = current_user.preferences or {}
        topics = prefs.get("topics", [])

        if not topics:
            raise HTTPException(
                status_code=400,
                detail="Please set your preferences (topics) before scraping articles"
            )

        # Scrape articles for the user
        result = user_scraper_service.scrape_for_user(
            db=db,
            user_id=current_user.id,
            max_articles_per_source=request.max_articles_per_source
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping articles: {str(e)}"
        )


@router.post("/scrape-for-me/background")
async def scrape_for_current_user_background(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scrape articles in the background (non-blocking)

    Use this endpoint when you want to trigger scraping without waiting for completion.
    The scraping will happen asynchronously and articles will appear in the database
    once processing is complete.
    """
    # Check if user has preferences set
    prefs = current_user.preferences or {}
    topics = prefs.get("topics", [])

    if not topics:
        raise HTTPException(
            status_code=400,
            detail="Please set your preferences (topics) before scraping articles"
        )

    # Add scraping task to background
    background_tasks.add_task(
        user_scraper_service.scrape_for_user,
        db=db,
        user_id=current_user.id,
        max_articles_per_source=request.max_articles_per_source
    )

    return {
        "success": True,
        "message": "Article scraping started in background. Articles will appear shortly.",
        "user_id": current_user.id,
        "topics": topics
    }


@router.get("/scraping-status")
async def get_scraping_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get information about articles available for the current user

    Returns statistics about how many articles are in the database
    that match the user's preferences.
    """
    from app.models.article import Article
    from sqlalchemy import func

    prefs = current_user.preferences or {}
    source_pref = prefs.get("source", "both")

    # Count articles by source type
    total_articles = db.query(func.count(Article.id)).scalar() or 0

    academic_count = db.query(func.count(Article.id))\
        .filter(Article.source_type == "academic").scalar() or 0

    industry_count = db.query(func.count(Article.id))\
        .filter(Article.source_type == "industry").scalar() or 0

    financial_count = db.query(func.count(Article.id))\
        .filter(Article.source_type == "financial").scalar() or 0

    # Calculate relevant articles for user
    relevant_count = 0
    if source_pref == "academic":
        relevant_count = academic_count
    elif source_pref == "industry":
        relevant_count = industry_count
    elif source_pref == "financial":
        relevant_count = financial_count
    else:  # both
        relevant_count = total_articles

    return {
        "user_id": current_user.id,
        "user_preferences": {
            "topics": prefs.get("topics", []),
            "keywords": prefs.get("keywords", []),
            "source_preference": source_pref
        },
        "database_stats": {
            "total_articles": total_articles,
            "academic_articles": academic_count,
            "industry_articles": industry_count,
            "financial_articles": financial_count,
            "relevant_for_user": relevant_count
        }
    }


@router.get("/my-history")
async def get_my_scraping_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's scraping job history

    Returns all scraping jobs for the current user,
    ordered by most recent first.
    """
    jobs = db.query(ScrapingJob).filter(
        ScrapingJob.user_id == current_user.id
    ).order_by(ScrapingJob.created_at.desc()).limit(50).all()

    return {
        "user_id": current_user.id,
        "total_jobs": len(jobs),
        "jobs": [job.to_dict() for job in jobs]
    }


@router.post("/admin/scrape-all-users")
async def scrape_for_all_users(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint: Scrape articles for all active users (administrator role required)
    """

    try:
        result = user_scraper_service.scrape_for_all_active_users(
            db=db,
            max_articles_per_source=request.max_articles_per_source
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping articles for all users: {str(e)}"
        )


# ==============================================================================
# Job-Based Background Scraping Endpoints
# ==============================================================================

def run_scraping_job_in_background(user_id: int, job_id: int, max_articles: int):
    """Background task to run scraping job"""
    db = SessionLocal()
    try:
        user_scraper_service.scrape_for_user_with_tracking(
            db=db,
            user_id=user_id,
            job_id=job_id,
            max_articles_per_source=max_articles
        )
    except Exception as e:
        print(f"Error in background scraping job {job_id}: {e}")
        # Job status already updated in scrape_for_user_with_tracking
    finally:
        db.close()


@router.post("/start-background-job")
async def start_background_scraping_job(
    request: ScrapeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a background scraping job with progress tracking

    Returns immediately with a job ID that can be used to check status.
    Uses a dedicated thread (not FastAPI BackgroundTasks) to ensure reliable execution.
    """
    # Check if user has preferences
    prefs = current_user.preferences or {}
    topics = prefs.get("topics", [])

    if not topics:
        raise HTTPException(
            status_code=400,
            detail="Please set your preferences (topics) before scraping articles"
        )

    # Check if user already has a running job
    existing_job = db.query(ScrapingJob).filter(
        ScrapingJob.user_id == current_user.id,
        ScrapingJob.status.in_(["pending", "running"])
    ).first()

    if existing_job:
        return {
            "job_id": existing_job.id,
            "message": "A scraping job is already in progress for your account",
            "status": existing_job.to_dict()
        }

    # Create new scraping job
    job = ScrapingJob(
        user_id=current_user.id,
        status="pending",
        current_step="queued",
        message="Your request is queued. We'll start finding articles shortly..."
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Use a dedicated thread instead of FastAPI BackgroundTasks for reliable execution
    # BackgroundTasks can be dropped by the server before executing on Railway
    thread = threading.Thread(
        target=run_scraping_job_in_background,
        args=(current_user.id, job.id, request.max_articles_per_source),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job.id,
        "message": "Scraping job started! Check status with /api/scraping/job-status/{job_id}",
        "status": job.to_dict()
    }


@router.get("/job-status/{job_id}")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the status of a scraping job

    Returns real-time progress and user-friendly messages
    """
    job = db.query(ScrapingJob).filter(
        ScrapingJob.id == job_id,
        ScrapingJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@router.get("/my-latest-job")
async def get_my_latest_job(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the latest scraping job for the current user

    Useful for checking if there's an ongoing job when user visits the page
    """
    latest_job = db.query(ScrapingJob).filter(
        ScrapingJob.user_id == current_user.id
    ).order_by(ScrapingJob.created_at.desc()).first()

    if not latest_job:
        return {
            "has_job": False,
            "message": "No scraping jobs found"
        }

    return {
        "has_job": True,
        "job": latest_job.to_dict(),
        "is_active": latest_job.status in ["pending", "running"]
    }


@router.post("/cancel-job/{job_id}")
async def cancel_scraping_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running or pending scraping job

    This endpoint:
    1. Verifies the job belongs to the current user
    2. Updates job status to 'cancelled'
    3. Sets completion timestamp
    4. The background task will check status and stop gracefully

    Returns success message
    """
    # Find the job
    job = db.query(ScrapingJob).filter(
        ScrapingJob.id == job_id,
        ScrapingJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if job can be cancelled
    if job.status in ["completed", "failed", "cancelled"]:
        return {
            "success": False,
            "message": f"Job already {job.status}. Cannot cancel.",
            "job": job.to_dict()
        }

    # Cancel the job
    job.status = "cancelled"
    job.current_step = "cancelled"
    job.message = "Analysis cancelled by user"
    job.completed_at = datetime.utcnow()
    job.error_message = None

    db.commit()
    db.refresh(job)

    return {
        "success": True,
        "message": "Analysis cancelled successfully",
        "job": job.to_dict()
    }
