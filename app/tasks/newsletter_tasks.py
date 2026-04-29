from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pytz import timezone as pytz_timezone, utc, all_timezones
from app.database import SessionLocal
from app.models.user import User
from app.models.newsletter import NewsletterLog
from app.models.notification import Notification
from app.models.scraping_job import ScrapingJob
from app.models.sent_article import SentArticle
from app.services.ranking import ranking_service
from app.services.email_service import email_service
from app.services.user_scraper import user_scraper_service
import threading


def has_fresh_articles(user: User, current_utc_time: datetime, db: Session) -> bool:
    """
    Check if user has fresh scraped articles based on their newsletter frequency.

    Args:
        user: User object
        current_utc_time: Current UTC datetime
        db: Database session

    Returns:
        True if user has recent articles, False if articles are stale
    """
    frequency = user.preferences.get('frequency', 'daily')

    # Get user's latest completed scraping job
    latest_job = db.query(ScrapingJob).filter(
        ScrapingJob.user_id == user.id,
        ScrapingJob.status == 'completed'
    ).order_by(ScrapingJob.completed_at.desc()).first()

    # No completed job = no fresh articles
    if not latest_job or not latest_job.completed_at:
        return False

    # Define freshness thresholds based on frequency
    if frequency == 'daily':
        threshold = current_utc_time - timedelta(hours=24)
    elif frequency == 'weekly':
        threshold = current_utc_time - timedelta(days=7)
    elif frequency == 'monthly':
        threshold = current_utc_time - timedelta(days=30)
    else:
        threshold = current_utc_time - timedelta(hours=24)  # Default to daily

    # Check if latest scraping job is fresh enough
    return latest_job.completed_at >= threshold


def trigger_background_scraping(user_id: int):
    """
    Trigger background scraping for a user in a separate thread.
    Used when user has stale articles but it's time for newsletter.
    """
    def scrape_task():
        db = SessionLocal()
        try:
            # Check for existing active jobs
            existing_job = db.query(ScrapingJob).filter(
                ScrapingJob.user_id == user_id,
                ScrapingJob.status.in_(['pending', 'running'])
            ).first()

            if existing_job:
                print(f"[Newsletter] User {user_id} already has active scraping job {existing_job.id}")
                return

            # Create new scraping job
            new_job = ScrapingJob(
                user_id=user_id,
                status='pending',
                created_at=datetime.utcnow(),
                current_step='Queued by newsletter scheduler',
                total_articles_found=0,
                articles_processed=0,
                articles_saved=0
            )
            db.add(new_job)
            db.commit()
            db.refresh(new_job)

            print(f"[Newsletter] Triggering background scraping for user {user_id} (job {new_job.id})")

            # Run scraping
            user_scraper_service.scrape_for_user_with_tracking(
                user_id=user_id,
                job_id=new_job.id,
                db=db
            )

        except Exception as e:
            print(f"[Newsletter] Error triggering scraping for user {user_id}: {e}")
            db.rollback()
        finally:
            db.close()

    # Start scraping in background thread
    thread = threading.Thread(target=scrape_task, daemon=True)
    thread.start()


def should_send_newsletter_to_user(user: User, current_utc_time: datetime, db: Session) -> tuple[bool, str]:
    """
    Check if newsletter should be sent to user based on their preferences, timezone, and article freshness.

    Args:
        user: User object
        current_utc_time: Current UTC datetime
        db: Database session

    Returns:
        Tuple of (should_send: bool, reason: str)
    """
    if not user.preferences:
        return False, "no preferences"

    frequency = user.preferences.get('frequency', 'daily')
    delivery_time = user.preferences.get('deliveryTime', '08:00')  # Default 8 AM local time
    delivery_day = user.preferences.get('deliveryDay', 'monday').lower()  # For weekly
    delivery_date = user.preferences.get('deliveryDate', 1)  # For monthly (1-28)
    user_timezone = user.preferences.get('timezone', 'UTC')  # Default to UTC

    # Validate and get user's timezone
    try:
        if user_timezone not in all_timezones:
            user_timezone = 'UTC'
        tz = pytz_timezone(user_timezone)
    except:
        tz = utc

    # Convert current UTC time to user's local time
    user_local_time = current_utc_time.astimezone(tz)

    # Parse delivery time (format: "HH:MM")
    try:
        delivery_hour, delivery_min = map(int, delivery_time.split(':'))
    except:
        delivery_hour, delivery_min = 8, 0  # Default to 8:00 AM

    # Check if current time in user's timezone matches their delivery time (within 1-hour window)
    time_matches = (user_local_time.hour == delivery_hour and abs(user_local_time.minute - delivery_min) < 60)

    if not time_matches:
        return False, "not scheduled time"

    # Get day of week in user's timezone
    current_day = user_local_time.strftime('%A').lower()

    # Check frequency
    frequency_matches = False
    if frequency == 'daily':
        frequency_matches = True
    elif frequency == 'weekly':
        frequency_matches = current_day == delivery_day
    elif frequency == 'monthly':
        frequency_matches = user_local_time.day == delivery_date

    if not frequency_matches:
        return False, f"not {frequency} delivery day"

    # NEW: Check if user has fresh articles
    if not has_fresh_articles(user, current_utc_time, db):
        return False, "stale articles"

    return True, "ready"


def generate_and_send_newsletters():
    """
    Generate personalized newsletters for eligible users based on their preferences

    This task:
    1. Gets all active users from database
    2. Checks each user's delivery preferences (time, frequency)
    3. For eligible users, ranks articles based on their preferences
    4. Generates personalized HTML newsletter
    5. Sends email via Gmail
    """
    # Get current UTC time with timezone awareness
    now_utc = datetime.now(utc)

    print(f"[{now_utc}] Starting newsletter generation task...")
    print(f"Current UTC time: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    db = SessionLocal()

    try:
        # Get all active users
        users = db.query(User).filter(User.is_active == True).all()
        print(f"Found {len(users)} active users")

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for user in users:
            try:
                # Check if user should receive newsletter at this time (with timezone and freshness support)
                should_send, reason = should_send_newsletter_to_user(user, now_utc, db)

                if not should_send:
                    # If articles are stale but it's the right time, trigger scraping
                    if reason == "stale articles":
                        print(f"User {user.email} has stale articles, triggering background scraping...")
                        trigger_background_scraping(user.id)

                    skipped_count += 1
                    continue

                # Skip users without preferences
                if not user.preferences:
                    print(f"Skipping user {user.email} - no preferences set")
                    skipped_count += 1
                    continue

                # Extract user preferences
                topics = user.preferences.get('topics', [])
                keywords = user.preferences.get('keywords', [])
                source_type = user.preferences.get('source', 'both')
                frequency = user.preferences.get('frequency', 'daily')

                # Skip if no topics/keywords
                if not topics and not keywords:
                    print(f"Skipping user {user.email} - no topics or keywords")
                    continue

                # Rank articles for this user
                print(f"Ranking articles for {user.email}...")
                ranked_articles = ranking_service.rank_articles_for_user(
                    db=db,
                    user_id=user.id,
                    user_topics=topics,
                    user_keywords=keywords,
                    source_type=source_type,
                    limit=10,  # Top 10 articles
                    exclude_sent=True  # Never resend an article
                )

                # Skip if no articles found
                if not ranked_articles:
                    print(f"No articles found for {user.email}")
                    continue

                # Send newsletter
                print(f"Sending newsletter to {user.email}...")
                success = email_service.send_newsletter(
                    to_email=user.email,
                    user_name=user.email.split('@')[0],  # Use email prefix as name
                    articles=ranked_articles,
                    frequency=frequency
                )

                if success:
                    sent_count += 1
                    print(f"✓ Newsletter sent to {user.email}")

                    # Record every delivered article so it won't be sent again
                    for article_dict in ranked_articles:
                        sa = SentArticle(
                            article_id=article_dict["id"],
                            user_id=user.id
                        )
                        db.merge(sa)
                    db.commit()

                    # Create notification for successful newsletter delivery
                    try:
                        notification = Notification(
                            user_id=user.id,
                            title="Newsletter Delivered",
                            message=f"Your personalized newsletter with {len(ranked_articles)} articles has been sent to {user.email}",
                            notification_type="success",
                            link="/history"  # Link to newsletter history
                        )
                        db.add(notification)
                        db.commit()
                        print(f"  → Notification created for {user.email}")
                    except Exception as notif_error:
                        print(f"  ⚠️  Error creating notification: {notif_error}")
                else:
                    failed_count += 1
                    print(f"✗ Failed to send newsletter to {user.email}")

                    # Create notification for failed newsletter delivery
                    try:
                        notification = Notification(
                            user_id=user.id,
                            title="Newsletter Delivery Failed",
                            message="We encountered an issue sending your newsletter. Please check your email settings or contact support.",
                            notification_type="error",
                            link="/preferences"
                        )
                        db.add(notification)
                        db.commit()
                    except Exception as notif_error:
                        print(f"  ⚠️  Error creating failure notification: {notif_error}")

            except Exception as e:
                failed_count += 1
                print(f"Error processing user {user.email}: {e}")
                continue

        print(f"Newsletter generation complete: {sent_count} sent, {failed_count} failed, {skipped_count} skipped (not scheduled for this time)")

        # Log the newsletter dispatch to database
        if sent_count > 0:
            try:
                log_entry = NewsletterLog(
                    subject=f"Daily IntelliNews Brief - {datetime.now().strftime('%B %d, %Y')}",
                    recipients=sent_count,
                    status="Completed"
                )
                db.add(log_entry)
                db.commit()
                print(f"✓ Newsletter dispatch logged to database")
            except Exception as log_error:
                print(f"Error logging newsletter dispatch: {log_error}")

    except Exception as e:
        print(f"Error in newsletter generation task: {e}")

    finally:
        db.close()


def send_test_newsletter(user_email: str):
    """
    Send a test newsletter to a specific user (for testing)

    Args:
        user_email: Email of the user to send test newsletter to
    """
    print(f"Sending test newsletter to {user_email}...")

    db = SessionLocal()

    try:
        # Find user
        user = db.query(User).filter(User.email == user_email).first()

        if not user:
            print(f"User {user_email} not found")
            return

        # Extract preferences
        topics = user.preferences.get('topics', ['AI', 'Machine Learning'])
        keywords = user.preferences.get('keywords', ['transformers', 'NLP'])
        source_type = user.preferences.get('source', 'both')

        # Rank articles
        ranked_articles = ranking_service.rank_articles_for_user(
            db=db,
            user_id=user.id,
            user_topics=topics,
            user_keywords=keywords,
            source_type=source_type,
            limit=5,  # Top 5 for testing
            exclude_sent=True  # Never resend an article
        )

        if not ranked_articles:
            print("No articles found")
            return

        # Send newsletter
        success = email_service.send_newsletter(
            to_email=user.email,
            user_name=user.email.split('@')[0],
            articles=ranked_articles,
            frequency="daily"
        )

        if success:
            print(f"✓ Test newsletter sent to {user_email}")
            # Record every delivered article so it won't be sent again
            for article_dict in ranked_articles:
                sa = SentArticle(
                    article_id=article_dict["id"],
                    user_id=user.id
                )
                db.merge(sa)
            db.commit()
        else:
            print(f"✗ Failed to send test newsletter")

    except Exception as e:
        print(f"Error sending test newsletter: {e}")

    finally:
        db.close()


def start_newsletter_scheduler():
    """
    Start background scheduler for automated newsletter generation

    Schedule:
    - Runs every hour to check which users should receive newsletters
    - Each user can set their own delivery time, frequency (daily/weekly/monthly), and day
    """
    scheduler = BackgroundScheduler()

    # Run every hour to check user preferences and send newsletters
    scheduler.add_job(
        generate_and_send_newsletters,
        'cron',
        minute=0,  # Run at the top of every hour
        id='hourly_newsletter_check'
    )

    scheduler.start()
    print("Newsletter scheduler started. Checking user preferences every hour for dynamic delivery.")

    return scheduler


# For manual testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Send test newsletter to specific email
        test_email = sys.argv[1]
        send_test_newsletter(test_email)
    else:
        # Generate newsletters for all users
        generate_and_send_newsletters()
