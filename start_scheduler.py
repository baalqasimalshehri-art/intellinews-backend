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

# Global scheduler reference
scheduler = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\n[Scheduler] Received shutdown signal. Stopping scheduler...")
    if scheduler:
        scheduler.shutdown()
    print("[Scheduler] Scheduler stopped. Exiting.")
    sys.exit(0)


def main():
    """
    Start the newsletter scheduler and keep it running
    """
    global scheduler

    print("=" * 60)
    print("IntelliNews Newsletter Scheduler")
    print("=" * 60)
    print("Starting newsletter scheduler...")
    print("Newsletters will be sent daily at 6:00 AM UTC")
    print("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start the scheduler
        scheduler = start_newsletter_scheduler()

        print("[Scheduler] Newsletter scheduler started successfully!")
        print("[Scheduler] Running in background. Press Ctrl+C to stop.")
        print("=" * 60)

        # Keep the script running
        while True:
            time.sleep(60)  # Sleep for 1 minute at a time
            # Print a heartbeat every hour
            current_time = time.localtime()
            if current_time.tm_min == 0:  # Every hour at 0 minutes
                print(f"[Scheduler] Heartbeat: Scheduler running at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    except KeyboardInterrupt:
        print("\n[Scheduler] Keyboard interrupt detected. Shutting down...")
        if scheduler:
            scheduler.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"[Scheduler] Error: {e}")
        if scheduler:
            scheduler.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
