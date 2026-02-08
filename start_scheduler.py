"""
Standalone scheduler process for Railway deployment

This script runs the APScheduler in a separate process to ensure
cron jobs continue running independently of the main FastAPI server.

For Railway deployment, this runs alongside the main API server.
"""
import time
import signal
import sys
from app.tasks.newsletter_tasks import start_newsletter_scheduler
from app.tasks.scraping_retry_tasks import start_retry_scheduler, shutdown_retry_scheduler

# Global scheduler references
newsletter_scheduler = None
retry_scheduler_active = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\n[Scheduler] Received shutdown signal. Stopping schedulers...")

    if newsletter_scheduler:
        print("[Scheduler] Stopping newsletter scheduler...")
        newsletter_scheduler.shutdown()

    if retry_scheduler_active:
        print("[Scheduler] Stopping retry scheduler...")
        shutdown_retry_scheduler()

    print("[Scheduler] All schedulers stopped. Exiting.")
    sys.exit(0)


def main():
    """
    Start the newsletter and retry schedulers and keep them running
    """
    global newsletter_scheduler, retry_scheduler_active

    print("=" * 60)
    print("IntelliNews Background Schedulers")
    print("=" * 60)
    print("Starting schedulers...")
    print("  1. Newsletter Scheduler (hourly checks)")
    print("  2. Scraping Retry Scheduler (every 30 minutes)")
    print("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start the newsletter scheduler
        print("[Scheduler] Starting newsletter scheduler...")
        newsletter_scheduler = start_newsletter_scheduler()
        print("[Scheduler] Newsletter scheduler started successfully!")

        # Start the retry scheduler
        print("[Scheduler] Starting scraping retry scheduler...")
        start_retry_scheduler()
        retry_scheduler_active = True
        print("[Scheduler] Scraping retry scheduler started successfully!")

        print("[Scheduler] All schedulers running. Press Ctrl+C to stop.")
        print("=" * 60)

        # Keep the script running
        while True:
            time.sleep(60)  # Sleep for 1 minute at a time
            # Print a heartbeat every hour
            current_time = time.localtime()
            if current_time.tm_min == 0:  # Every hour at 0 minutes
                print(f"[Scheduler] Heartbeat: All schedulers running at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    except KeyboardInterrupt:
        print("\n[Scheduler] Keyboard interrupt detected. Shutting down...")
        if newsletter_scheduler:
            newsletter_scheduler.shutdown()
        if retry_scheduler_active:
            shutdown_retry_scheduler()
        sys.exit(0)
    except Exception as e:
        print(f"[Scheduler] Error: {e}")
        if newsletter_scheduler:
            newsletter_scheduler.shutdown()
        if retry_scheduler_active:
            shutdown_retry_scheduler()
        sys.exit(1)


if __name__ == "__main__":
    main()
