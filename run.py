#!/usr/bin/env python
"""
IntelliNews Backend Runner

This script helps you quickly run different backend tasks.
"""

import sys
import subprocess


def print_menu():
    """Print main menu"""
    print("\n" + "="*60)
    print("📰 IntelliNews Backend")
    print("="*60)
    print("\n Choose an option:\n")
    print("  1. Start API server (development mode)")
    print("  2. Initialize database")
    print("  3. Run article scraper")
    print("  4. Send test newsletter")
    print("  5. Check database status")
    print("  6. View API documentation")
    print("  0. Exit")
    print("\n" + "="*60)


def start_server():
    """Start FastAPI server in development mode"""
    print("\n🚀 Starting FastAPI server...")
    print("API will be available at: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server\n")
    subprocess.run(["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])


def init_database():
    """Initialize database with pgvector and create tables"""
    print("\n🗄️  Initializing database...")
    subprocess.run([sys.executable, "-c", "from app.database import init_db; init_db()"])
    print("\n✓ Database initialized successfully!")


def run_scraper():
    """Run article scraper manually"""
    print("\n🕷️  Starting article scraper...")
    print("This will scrape articles from all sources and may take 10-20 minutes.\n")
    confirm = input("Continue? (y/n): ")

    if confirm.lower() == 'y':
        subprocess.run([sys.executable, "-m", "app.tasks.scraper_tasks"])
    else:
        print("Cancelled.")


def send_test_newsletter():
    """Send test newsletter to an email"""
    print("\n📧 Send Test Newsletter")
    email = input("Enter email address: ")

    if email:
        print(f"\nSending test newsletter to {email}...")
        subprocess.run([sys.executable, "-m", "app.tasks.newsletter_tasks", email])
    else:
        print("No email provided. Cancelled.")


def check_database():
    """Check database status"""
    print("\n🗄️  Checking database status...")

    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            # Check connection
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"\n✓ PostgreSQL Connection: OK")
            print(f"  Version: {version}")

            # Check pgvector
            result = conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector';"))
            if result.fetchone():
                print("✓ pgvector Extension: Installed")
            else:
                print("✗ pgvector Extension: NOT installed")

            # Check tables
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]

            print(f"\n✓ Tables ({len(tables)}):")
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table};"))
                count = result.fetchone()[0]
                print(f"  - {table}: {count} rows")

        print("\n✓ Database is healthy!")

    except Exception as e:
        print(f"\n✗ Database error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your DATABASE_URL in .env file")
        print("3. Run: brew services start postgresql@15 (macOS)")


def view_docs():
    """Open API documentation in browser"""
    import webbrowser
    print("\n📚 Opening API documentation in browser...")
    webbrowser.open("http://localhost:8000/docs")
    print("Note: Make sure the server is running (option 1)")


def main():
    """Main entry point"""
    while True:
        print_menu()
        choice = input("\nEnter your choice (0-6): ").strip()

        if choice == "1":
            start_server()
        elif choice == "2":
            init_database()
        elif choice == "3":
            run_scraper()
        elif choice == "4":
            send_test_newsletter()
        elif choice == "5":
            check_database()
        elif choice == "6":
            view_docs()
        elif choice == "0":
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        else:
            print("\n❌ Invalid choice. Please try again.")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
