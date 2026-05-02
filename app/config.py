from pydantic_settings import BaseSettings
from typing import Optional
from datetime import datetime


class Settings(BaseSettings):
    """Application configuration using Pydantic settings"""

    # Database
    DATABASE_URL: str

    # OpenAI
    OPENAI_API_KEY: str

    # Email (Resend API)
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "IntelliNews <newsletter@alshehri050.shop>"

    # Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production-please-use-a-strong-random-key"

    # Application
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    FRONTEND_URL: str = "http://localhost:5173"

    # Scraping
    ARXIV_MAX_RESULTS: int = 100

    # Recency Filter
    MIN_ARTICLE_DATE: str = "2025-01-01"

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 1536

    # GPT
    GPT_MODEL: str = "gpt-4o-mini"
    MAX_TOKENS: int = 1000

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def min_article_datetime(self) -> datetime:
        """Parse MIN_ARTICLE_DATE to datetime object"""
        return datetime.strptime(self.MIN_ARTICLE_DATE, "%Y-%m-%d")

    @property
    def database_url(self) -> str:
        """Get database URL with correct dialect for SQLAlchemy 2.0"""
        # SQLAlchemy 2.0 requires postgresql:// instead of postgres://
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL


# Global settings instance
settings = Settings()
