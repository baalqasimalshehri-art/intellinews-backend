from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings

# Create database engine with optimized connection pooling
engine = create_engine(
    settings.database_url,  # Use property that converts postgres:// to postgresql://
    poolclass=QueuePool,
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Maximum overflow connections
    pool_timeout=30,  # Timeout for getting connection from pool
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Test connections before using
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database with pgvector extension and create tables"""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Enable pgvector extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Import all models to ensure they're registered
    from app.models import (
        Article, User, Ranking, PasswordResetToken, NewsletterLog,
        SystemSettings, RSSFeed, Notification, ScrapingJob
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Migration: add user_id to newsletter_logs if it doesn't exist (for per-user tracking)
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE newsletter_logs
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        """))
        conn.commit()
