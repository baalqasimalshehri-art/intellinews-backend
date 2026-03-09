"""
Scraping Retry Scheduler

Automatically retries scraping for users who cancelled their jobs.
Runs every 30 minutes to check for cancelled jobs and trigger new scraping.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.scraping_job import ScrapingJob
from app.models.user import User
from app.services.user_scraper import user_scraper_service
import logging

logger = logging.getLogger(__name__)

# Global scheduler instance
retry_scheduler = BackgroundScheduler()


def retry_cancelled_scraping_jobs():
    """
    Check for failed or cancelled scraping jobs older than 30 minutes
    and automatically trigger new scraping for those users.
    """
    db: Session = SessionLocal()
    try:
        logger.info("[Retry Scheduler] Checking for failed/cancelled jobs to retry...")

        # Get current time and 30-minute threshold
        now = datetime.utcnow()
        retry_threshold = now - timedelta(minutes=30)

        # Query for failed OR cancelled jobs older than 30 minutes
        cancelled_jobs = db.query(ScrapingJob).filter(
            ScrapingJob.status.in_(['cancelled', 'failed']),
            ScrapingJob.completed_at < retry_threshold
        ).all()

        logger.info(f"[Retry Scheduler] Found {len(cancelled_jobs)} failed/cancelled jobs older than 30 minutes")

        retry_count = 0
        skip_count = 0
        processed_users = set()  # Only retry once per user per cycle

        for job in cancelled_jobs:
            try:
                # Only process each user once per cycle (they may have multiple cancelled jobs)
                if job.user_id in processed_users:
                    continue
                processed_users.add(job.user_id)

                # Get user
                user = db.query(User).filter(User.id == job.user_id).first()

                if not user:
                    logger.warning(f"[Retry Scheduler] User {job.user_id} not found, skipping job {job.id}")
                    skip_count += 1
                    continue

                # Check if user still has preferences
                if not user.preferences or not user.preferences.get('topics'):
                    logger.info(f"[Retry Scheduler] User {user.email} has no topics, skipping retry")
                    skip_count += 1
                    continue

                # Check for existing active jobs (prevent duplicates)
                existing_job = db.query(ScrapingJob).filter(
                    ScrapingJob.user_id == user.id,
                    ScrapingJob.status.in_(['pending', 'running'])
                ).first()

                if existing_job:
                    logger.info(f"[Retry Scheduler] User {user.email} already has active job {existing_job.id}, skipping")
                    skip_count += 1
                    continue

                # Skip if user already had a successful scrape within 6 hours (respect 6-hour cadence)
                six_hours_ago = now - timedelta(hours=6)
                recent_completed = db.query(ScrapingJob).filter(
                    ScrapingJob.user_id == user.id,
                    ScrapingJob.status == 'completed',
                    ScrapingJob.completed_at >= six_hours_ago
                ).first()

                if recent_completed:
                    logger.info(f"[Retry Scheduler] User {user.email} completed scraping within 6h, skipping retry")
                    skip_count += 1
                    continue

                # Create new scraping job
                new_job = ScrapingJob(
                    user_id=user.id,
                    status='pending',
                    created_at=now,
                    current_step='Queued for retry',
                    total_articles_found=0,
                    articles_processed=0,
                    articles_saved=0
                )
                db.add(new_job)
                db.commit()
                db.refresh(new_job)

                logger.info(f"[Retry Scheduler] Created retry job {new_job.id} for user {user.email}")

                # Trigger scraping in background (non-blocking)
                # Use a separate session for the background task
                _run_scraping_in_background(new_job.id)

                retry_count += 1

            except Exception as e:
                logger.error(f"[Retry Scheduler] Error processing job {job.id}: {e}")
                db.rollback()
                continue

        logger.info(f"[Retry Scheduler] Summary: {retry_count} jobs retried, {skip_count} skipped")

    except Exception as e:
        logger.error(f"[Retry Scheduler] Error in retry task: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        db.close()


def cleanup_stuck_pending_jobs():
    """
    Find pending jobs older than 30 minutes and mark them as failed.
    This prevents jobs from being stuck in pending forever.
    """
    db: Session = SessionLocal()
    try:
        logger.info("[Retry Scheduler] Checking for stuck pending jobs...")

        # Get current time
        now = datetime.utcnow()
        timeout_threshold = now - timedelta(minutes=30)

        # Find pending jobs older than 30 minutes
        stuck_jobs = db.query(ScrapingJob).filter(
            ScrapingJob.status == 'pending',
            ScrapingJob.created_at < timeout_threshold
        ).all()

        logger.info(f"[Retry Scheduler] Found {len(stuck_jobs)} stuck pending jobs")

        for job in stuck_jobs:
            try:
                # Mark as failed
                job.status = 'failed'
                job.error_message = 'Job timed out in pending status (>30 minutes)'
                job.completed_at = now
                job.current_step = 'timeout'
                job.message = 'Job timed out and was automatically cancelled'

                # Create notification for user
                from app.models.notification import Notification
                notification = Notification(
                    user_id=job.user_id,
                    title="⚠️ Scraping Job Timed Out",
                    message="A scraping job timed out. The system will automatically retry in the next scheduled cycle (every 6 hours).",
                    notification_type="warning",
                    link="/history"
                )
                db.add(notification)

                logger.info(f"[Retry Scheduler] Marked job {job.id} as failed (timeout)")

            except Exception as e:
                logger.error(f"[Retry Scheduler] Error marking job {job.id} as failed: {e}")
                db.rollback()
                continue

        db.commit()
        logger.info(f"[Retry Scheduler] Cleaned up {len(stuck_jobs)} stuck jobs")

    except Exception as e:
        logger.error(f"[Retry Scheduler] Error in cleanup task: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        db.close()


def _run_scraping_in_background(job_id: int):
    """
    Run scraping in background thread for a specific job.
    Uses a new database session to avoid conflicts.
    """
    import threading

    def scrape_task():
        db_task: Session = SessionLocal()
        try:
            # Get job and user
            job = db_task.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if not job:
                logger.error(f"[Background Scrape] Job {job_id} not found")
                return

            user = db_task.query(User).filter(User.id == job.user_id).first()
            if not user:
                logger.error(f"[Background Scrape] User for job {job_id} not found")
                return

            # Run scraping with tracking
            logger.info(f"[Background Scrape] Starting scraping for job {job_id}, user {user.email}")
            user_scraper_service.scrape_for_user_with_tracking(
                user_id=user.id,
                job_id=job_id,
                db=db_task
            )
            logger.info(f"[Background Scrape] Completed scraping for job {job_id}")

        except Exception as e:
            logger.error(f"[Background Scrape] Error in scraping task for job {job_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Mark job as failed
            try:
                job = db_task.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    db_task.commit()
            except Exception as commit_error:
                logger.error(f"[Background Scrape] Error updating failed job: {commit_error}")
                db_task.rollback()
        finally:
            db_task.close()

    # Start thread
    thread = threading.Thread(target=scrape_task, daemon=True)
    thread.start()


def start_retry_scheduler():
    """
    Initialize and start the retry scheduler.
    Runs every 30 minutes.
    """
    logger.info("[Retry Scheduler] Initializing scraping retry scheduler...")

    # Job 1: Retry cancelled jobs
    retry_scheduler.add_job(
        retry_cancelled_scraping_jobs,
        'cron',
        minute='0,30',  # Run at 0 and 30 minutes of every hour
        id='scraping_retry_check',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    # Job 2: Clean up stuck pending jobs
    retry_scheduler.add_job(
        cleanup_stuck_pending_jobs,
        'cron',
        minute='0,30',  # Run at 0 and 30 minutes of every hour
        id='cleanup_stuck_pending',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    # Start scheduler
    retry_scheduler.start()
    logger.info("[Retry Scheduler] ✓ Started (runs at :00 and :30)")
    logger.info("[Retry Scheduler] - Retrying cancelled jobs")
    logger.info("[Retry Scheduler] - Cleaning stuck pending jobs")


def shutdown_retry_scheduler():
    """
    Gracefully shutdown the retry scheduler.
    """
    if retry_scheduler.running:
        logger.info("[Retry Scheduler] Shutting down retry scheduler...")
        retry_scheduler.shutdown(wait=True)
        logger.info("[Retry Scheduler] Retry scheduler shut down successfully")
