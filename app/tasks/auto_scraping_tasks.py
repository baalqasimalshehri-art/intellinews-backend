"""
Auto-Scraping Scheduler

Automatically scrapes fresh articles for all active users every 6 hours.
Ensures users always have up-to-date content without manual intervention.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.models.scraping_job import ScrapingJob
from app.models.notification import Notification
from app.services.user_scraper import user_scraper_service
import logging

logger = logging.getLogger(__name__)

# Global scheduler instance
auto_scraper = BackgroundScheduler()


def auto_scrape_for_all_users():
    """
    Run automatic scraping for all active users with preferences.
    Creates notifications for users when scraping starts/completes.
    """
    db: Session = SessionLocal()
    try:
        logger.info("[Auto-Scraper] Starting 6-hour automatic scraping cycle...")

        # Get all active users with topics
        active_users = db.query(User).filter(
            User.is_active == True,
            User.preferences.isnot(None)
        ).all()

        # Filter users who have topics
        users_with_topics = [
            user for user in active_users
            if user.preferences.get('topics') and len(user.preferences.get('topics', [])) > 0
        ]

        logger.info(f"[Auto-Scraper] Found {len(users_with_topics)} users to scrape")

        scraped_count = 0
        skipped_count = 0

        for user in users_with_topics:
            try:
                # Check for existing active jobs (prevent duplicates)
                existing_job = db.query(ScrapingJob).filter(
                    ScrapingJob.user_id == user.id,
                    ScrapingJob.status.in_(['pending', 'running'])
                ).first()

                if existing_job:
                    logger.info(f"[Auto-Scraper] User {user.email} already has active job {existing_job.id}, skipping")
                    skipped_count += 1
                    continue

                # Create new scraping job
                now = datetime.utcnow()
                new_job = ScrapingJob(
                    user_id=user.id,
                    status='pending',
                    created_at=now,
                    current_step='Queued by auto-scraper',
                    message='🔄 Automatic scraping started every 6 hours',
                    total_articles_found=0,
                    articles_processed=0,
                    articles_saved=0
                )
                db.add(new_job)
                db.commit()
                db.refresh(new_job)

                logger.info(f"[Auto-Scraper] Created job {new_job.id} for user {user.email}")

                # Create notification for user
                notification = Notification(
                    user_id=user.id,
                    title="🔄 Auto-Scraping Started",
                    message=f"Finding fresh articles based on your interests: {', '.join(user.preferences.get('topics', [])[:3])}...",
                    type="info",
                    is_read=False,
                    created_at=now
                )
                db.add(notification)
                db.commit()

                # Trigger scraping in background
                _run_scraping_in_background(new_job.id)

                scraped_count += 1

            except Exception as e:
                logger.error(f"[Auto-Scraper] Error processing user {user.id}: {e}")
                db.rollback()
                continue

        logger.info(f"[Auto-Scraper] Summary: {scraped_count} jobs started, {skipped_count} skipped")

    except Exception as e:
        logger.error(f"[Auto-Scraper] Error in auto-scraping task: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        db.close()


def _run_scraping_in_background(job_id: int):
    """
    Run scraping in background thread for a specific job.
    Creates completion notification when done.
    """
    import threading

    def scrape_task():
        db_task: Session = SessionLocal()
        try:
            # Get job and user
            job = db_task.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if not job:
                logger.error(f"[Auto-Scraper] Job {job_id} not found")
                return

            user = db_task.query(User).filter(User.id == job.user_id).first()
            if not user:
                logger.error(f"[Auto-Scraper] User for job {job_id} not found")
                return

            # Run scraping with tracking
            logger.info(f"[Auto-Scraper] Starting scraping for job {job_id}, user {user.email}")
            user_scraper_service.scrape_for_user_with_tracking(
                user_id=user.id,
                job_id=job_id,
                db=db_task
            )
            logger.info(f"[Auto-Scraper] Completed scraping for job {job_id}")

            # Refresh job to get latest stats
            db_task.refresh(job)

            # Create success notification
            if job.status == 'completed':
                notification = Notification(
                    user_id=user.id,
                    title="✅ Auto-Scraping Complete",
                    message=f"Found {job.articles_saved} new articles! Check your Dashboard to explore.",
                    type="success",
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db_task.add(notification)
                db_task.commit()

        except Exception as e:
            logger.error(f"[Auto-Scraper] Error in scraping task for job {job_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Mark job as failed and notify user
            try:
                job = db_task.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()

                    # Create error notification
                    notification = Notification(
                        user_id=job.user_id,
                        title="❌ Auto-Scraping Failed",
                        message="Something went wrong during automatic scraping. Please try manual scraping.",
                        type="error",
                        is_read=False,
                        created_at=datetime.utcnow()
                    )
                    db_task.add(notification)
                    db_task.commit()
            except Exception as commit_error:
                logger.error(f"[Auto-Scraper] Error updating failed job: {commit_error}")
                db_task.rollback()
        finally:
            db_task.close()

    # Start thread
    thread = threading.Thread(target=scrape_task, daemon=True)
    thread.start()


def start_auto_scraper():
    """
    Initialize and start the 6-hour auto-scraping scheduler.
    Runs at 0, 6, 12, 18 hours (4 times per day).
    """
    logger.info("[Auto-Scraper] Initializing 6-hour auto-scraping scheduler...")

    # Add job to run every 6 hours
    auto_scraper.add_job(
        auto_scrape_for_all_users,
        'cron',
        hour='0,6,12,18',  # Run at midnight, 6am, noon, 6pm UTC
        id='auto_scraping_6hour',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    # Start scheduler
    auto_scraper.start()
    logger.info("[Auto-Scraper] Auto-scraper started (runs every 6 hours at 00:00, 06:00, 12:00, 18:00 UTC)")


def shutdown_auto_scraper():
    """
    Gracefully shutdown the auto-scraper.
    """
    if auto_scraper.running:
        logger.info("[Auto-Scraper] Shutting down auto-scraper...")
        auto_scraper.shutdown(wait=True)
        logger.info("[Auto-Scraper] Auto-scraper shut down successfully")
