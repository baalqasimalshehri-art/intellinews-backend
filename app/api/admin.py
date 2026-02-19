"""Admin API endpoints for system management"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

from passlib.context import CryptContext

from app.database import get_db
from app.models.user import User
from app.models.article import Article
from app.models.newsletter import NewsletterLog
from app.models.settings import SystemSettings
from app.utils.admin import require_admin
from app.tasks.newsletter_tasks import send_test_newsletter, generate_and_send_newsletters

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== PYDANTIC SCHEMAS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class NewsletterLogCreate(BaseModel):
    subject: str
    recipients: int
    status: str = "Completed"


class SystemSettingsUpdate(BaseModel):
    key: str
    value: Any  # Can be dict, list, string, etc.


class ArticleCreate(BaseModel):
    title: str
    source: str
    summary: str


# ==================== USER MANAGEMENT ====================

@router.get("/users")
async def get_all_users(
    search: Optional[str] = Query(None, description="Search by email"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    try:
        query = db.query(User)

        if search:
            query = query.filter(User.email.ilike(f"%{search}%"))

        users = query.order_by(desc(User.created_at)).all()

        return {
            "success": True,
            "users": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "name": u.email.split('@')[0],
                    "role": u.role,
                    "status": "Active" if u.is_active else "Disabled",
                    "topics": u.preferences.get("topics", []) if u.preferences else [],
                    "joinDate": u.created_at.isoformat() if u.created_at else None
                }
                for u in users
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


@router.post("/users")
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Create new user
        new_user = User(
            email=user_data.email,
            hashed_password=pwd_context.hash(user_data.password),
            role=user_data.role,
            is_active=True,
            is_verified=True
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


@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Toggle user active status (admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent admin from disabling themselves
        if user.id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot disable your own account")

        user.is_active = not user.is_active
        db.commit()

        return {
            "success": True,
            "message": f"User {'activated' if user.is_active else 'disabled'} successfully",
            "status": "Active" if user.is_active else "Disabled"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user and all related data (admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent admin from deleting themselves
        if user.id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")

        # Delete related records first to avoid foreign key constraint violations
        # Using text() for raw SQL to ensure proper execution
        from sqlalchemy import text

        # Delete rankings
        db.execute(text("DELETE FROM rankings WHERE user_id = :user_id"), {"user_id": user_id})

        # Delete scraping jobs
        db.execute(text("DELETE FROM scraping_jobs WHERE user_id = :user_id"), {"user_id": user_id})

        # Delete password reset tokens
        db.execute(text("DELETE FROM password_reset_tokens WHERE user_id = :user_id"), {"user_id": user_id})

        # Delete notifications
        db.execute(text("DELETE FROM notifications WHERE user_id = :user_id"), {"user_id": user_id})

        # Now delete the user
        db.delete(user)
        db.commit()

        return {
            "success": True,
            "message": "User and all related data deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


# ==================== ANALYTICS ====================

@router.get("/analytics")
async def get_analytics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system analytics and metrics (admin only)"""
    try:
        # Total users
        total_users = db.query(func.count(User.id)).scalar()

        # Active users
        active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()

        # Total articles
        total_articles = db.query(func.count(Article.id)).scalar()

        # Articles in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_articles = db.query(func.count(Article.id)).filter(
            Article.scraped_at >= week_ago
        ).scalar()

        # Total newsletters sent
        total_newsletters = db.query(func.count(NewsletterLog.id)).scalar()

        # Topic distribution
        topic_stats = {}
        users_with_prefs = db.query(User).filter(User.preferences.isnot(None)).all()
        for user in users_with_prefs:
            topics = user.preferences.get("topics", []) if user.preferences else []
            for topic in topics:
                topic_stats[topic] = topic_stats.get(topic, 0) + 1

        return {
            "success": True,
            "metrics": {
                "totalUsers": total_users,
                "activeUsers": active_users,
                "totalArticles": total_articles,
                "recentArticles": recent_articles,
                "totalNewsletters": total_newsletters
            },
            "topicEngagement": [
                {"topic": topic, "count": count, "percentage": round(count / total_users * 100, 1) if total_users > 0 else 0}
                for topic, count in sorted(topic_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analytics: {str(e)}")


# ==================== NEWSLETTER LOGS ====================

@router.get("/newsletters")
async def get_newsletter_logs(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get newsletter dispatch logs (admin only)"""
    try:
        logs = db.query(NewsletterLog).order_by(desc(NewsletterLog.created_at)).limit(limit).all()

        return {
            "success": True,
            "newsletters": [log.to_dict() for log in logs]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching newsletters: {str(e)}")


@router.post("/newsletters")
async def create_newsletter_log(
    log_data: NewsletterLogCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a newsletter log entry (admin only)"""
    try:
        new_log = NewsletterLog(
            subject=log_data.subject,
            recipients=log_data.recipients,
            status=log_data.status
        )

        db.add(new_log)
        db.commit()
        db.refresh(new_log)

        return {
            "success": True,
            "message": "Newsletter log created successfully",
            "log": new_log.to_dict()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating newsletter log: {str(e)}")


@router.delete("/newsletters/{log_id}")
async def delete_newsletter_log(
    log_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a newsletter log (admin only)"""
    try:
        log = db.query(NewsletterLog).filter(NewsletterLog.id == log_id).first()
        if not log:
            raise HTTPException(status_code=404, detail="Newsletter log not found")

        db.delete(log)
        db.commit()

        return {
            "success": True,
            "message": "Newsletter log deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting log: {str(e)}")


# ==================== ARTICLES (CONTENT) ====================

@router.get("/articles")
async def get_all_articles(
    limit: int = Query(100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all articles for admin content management"""
    try:
        articles = db.query(Article).order_by(desc(Article.scraped_at)).limit(limit).all()

        return {
            "success": True,
            "articles": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "source": a.source or "Unknown",
                    "summary": a.summary or "",
                    "tags": a.tags or [],
                    "date": a.scraped_at.isoformat() if a.scraped_at else None
                }
                for a in articles
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching articles: {str(e)}")


@router.post("/articles")
async def create_article(
    article_data: ArticleCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new article (admin only)"""
    try:
        new_article = Article(
            title=article_data.title,
            source=article_data.source,
            summary=article_data.summary,
            url=f"https://example.com/article/{article_data.title.lower().replace(' ', '-')}",  # Placeholder URL
            tags=["New"],
            category="General"
        )

        db.add(new_article)
        db.commit()
        db.refresh(new_article)

        return {
            "success": True,
            "message": "Article created successfully",
            "article": {
                "id": str(new_article.id),
                "title": new_article.title,
                "source": new_article.source,
                "summary": new_article.summary,
                "tags": new_article.tags,
                "date": new_article.scraped_at.isoformat() if new_article.scraped_at else None
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating article: {str(e)}")


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete an article and all related data (admin only)"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Delete related records first to avoid foreign key constraint violations
        # Delete rankings associated with this article
        db.execute(text("DELETE FROM rankings WHERE article_id = :article_id"), {"article_id": article_id})

        # Now delete the article
        db.delete(article)
        db.commit()

        return {
            "success": True,
            "message": "Article and all related data deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting article: {str(e)}")


# ==================== SYSTEM SETTINGS ====================

@router.get("/settings")
async def get_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all system settings (admin only)"""
    try:
        settings = db.query(SystemSettings).all()

        settings_dict = {s.key: s.value for s in settings}

        # Provide defaults if not set
        if "sources" not in settings_dict:
            settings_dict["sources"] = []
        if "schedule" not in settings_dict:
            settings_dict["schedule"] = "09:00"
        if "smtp" not in settings_dict:
            settings_dict["smtp"] = ""

        return {
            "success": True,
            "settings": settings_dict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.put("/settings")
async def update_settings(
    settings_data: SystemSettingsUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update system settings (admin only)"""
    try:
        # If updating sources, validate RSS feeds
        if settings_data.key == "sources" and isinstance(settings_data.value, list):
            import feedparser
            valid_sources = []

            for source in settings_data.value:
                try:
                    # Try to parse the feed to validate it
                    feed = feedparser.parse(source)
                    if feed.bozo == 0 or len(feed.entries) > 0:
                        # Feed is valid or has entries
                        valid_sources.append(source)
                    else:
                        print(f"Warning: Feed {source} may be invalid but adding anyway")
                        valid_sources.append(source)
                except Exception as e:
                    print(f"Error validating feed {source}: {e}")
                    # Add anyway but log the error
                    valid_sources.append(source)

            settings_data.value = valid_sources

        setting = db.query(SystemSettings).filter(SystemSettings.key == settings_data.key).first()

        if setting:
            setting.value = settings_data.value
        else:
            setting = SystemSettings(key=settings_data.key, value=settings_data.value)
            db.add(setting)

        db.commit()

        return {
            "success": True,
            "message": "Settings updated successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")


# ==================== JOBS/PIPELINES ====================

@router.get("/jobs")
async def get_jobs(
    admin: User = Depends(require_admin)
):
    """Get system jobs status (admin only)"""
    # For now, return static jobs - can be extended with real job tracking
    return {
        "success": True,
        "jobs": [
            {
                "id": "job-1",
                "name": "Article Scraper",
                "status": "Success",
                "time": "2 hours ago"
            },
            {
                "id": "job-2",
                "name": "Newsletter Generator",
                "status": "Success",
                "time": "4 hours ago"
            },
            {
                "id": "job-3",
                "name": "Preference Sync",
                "status": "Success",
                "time": "6 hours ago"
            }
        ]
    }


# ==================== NEWSLETTER OPERATIONS ====================

class SendNewsletterRequest(BaseModel):
    email: Optional[EmailStr] = None  # If provided, send to specific user; otherwise send to all


@router.post("/send-newsletter")
async def send_newsletter(
    request: SendNewsletterRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Send newsletter to specific user or all users (admin only)

    If email is provided, sends test newsletter to that user.
    If email is omitted, sends newsletter to all active users in background.
    """
    try:
        if request.email:
            # Send test newsletter to specific user (synchronous for immediate feedback)
            user = db.query(User).filter(User.email == request.email).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User {request.email} not found")

            # Use the newsletter task function
            send_test_newsletter(request.email)

            return {
                "success": True,
                "message": f"Test newsletter sent to {request.email}"
            }
        else:
            # Send to all users in background (non-blocking), force=True bypasses schedule checks
            import threading
            thread = threading.Thread(target=generate_and_send_newsletters, kwargs={"force": True}, daemon=True)
            thread.start()

            return {
                "success": True,
                "message": "Newsletter job started. Emails will be sent to all active users in the background."
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending newsletter: {str(e)}")


# ==================== RSS FEED MANAGEMENT ====================

class RSSFeedCreate(BaseModel):
    name: str
    url: str
    source_type: str  # "academic", "financial", "industry"


class RSSFeedUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/rss-feeds")
async def list_rss_feeds(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all RSS feeds"""
    from app.models.rss_feed import RSSFeed

    feeds = db.query(RSSFeed).all()
    return {
        "success": True,
        "feeds": [{
            "id": feed.id,
            "name": feed.name,
            "url": feed.url,
            "source_type": feed.source_type.value,
            "is_active": feed.is_active,
            "created_at": feed.created_at
        } for feed in feeds]
    }


@router.post("/rss-feeds")
async def create_rss_feed(
    feed_data: RSSFeedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new RSS feed"""
    from app.models.rss_feed import RSSFeed, SourceType

    # Validate source_type
    try:
        source_type_enum = SourceType[feed_data.source_type]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: academic, financial, industry"
        )

    # Check if feed already exists
    existing = db.query(RSSFeed).filter(
        (RSSFeed.url == feed_data.url) | (RSSFeed.name == feed_data.name)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Feed with this name or URL already exists")

    # Create new feed
    new_feed = RSSFeed(
        name=feed_data.name,
        url=feed_data.url,
        source_type=source_type_enum
    )

    db.add(new_feed)
    db.commit()
    db.refresh(new_feed)

    return {
        "success": True,
        "message": "RSS feed created successfully",
        "feed": {
            "id": new_feed.id,
            "name": new_feed.name,
            "url": new_feed.url,
            "source_type": new_feed.source_type.value,
            "is_active": new_feed.is_active
        }
    }


@router.patch("/rss-feeds/{feed_id}")
async def update_rss_feed(
    feed_id: int,
    feed_update: RSSFeedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update an RSS feed"""
    from app.models.rss_feed import RSSFeed

    feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    # Update fields
    if feed_update.name is not None:
        feed.name = feed_update.name
    if feed_update.url is not None:
        feed.url = feed_update.url
    if feed_update.is_active is not None:
        feed.is_active = feed_update.is_active

    db.commit()
    db.refresh(feed)

    return {
        "success": True,
        "message": "RSS feed updated successfully",
        "feed": {
            "id": feed.id,
            "name": feed.name,
            "url": feed.url,
            "source_type": feed.source_type.value,
            "is_active": feed.is_active
        }
    }


@router.delete("/rss-feeds/{feed_id}")
async def delete_rss_feed(
    feed_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete an RSS feed"""
    from app.models.rss_feed import RSSFeed

    feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    db.delete(feed)
    db.commit()

    return {
        "success": True,
        "message": "RSS feed deleted successfully"
    }
