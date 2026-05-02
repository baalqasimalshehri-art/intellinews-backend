import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api import articles, users, auth, scraping, admin, notifications
from app.database import init_db
from app.config import settings
from app.utils.cache import get_cache_stats
from app.utils.init_admin import create_default_admin
from app.utils.init_feeds import create_default_feeds

# Create FastAPI application
app = FastAPI(
    title="IntelliNews API",
    description="AI-Driven Smart Newsletter System with RAG retrieval and intelligent ranking",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(auth.router)
app.include_router(articles.router)
app.include_router(users.router)
app.include_router(scraping.router)
app.include_router(admin.router)
app.include_router(notifications.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")

    # Create default admin user
    print("\nChecking for default admin user...")
    create_default_admin()

    # Initialize default RSS feeds
    print("\nInitializing default RSS feeds...")
    create_default_feeds()

    # Re-summarise articles that have empty summaries (runs in background, non-blocking)
    from app.tasks.scraper_tasks import resummarize_empty_articles
    thread = threading.Thread(target=resummarize_empty_articles, daemon=True)
    thread.start()
    print("\nStarted background re-summarization of articles with empty summaries.")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "IntelliNews API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "RAG-style retrieval with pgvector",
            "Context-aware AI summarization (Academic/Industry/Financial)",
            "AI-driven ranking with explainability",
            "Recency filtering (2025+ articles)",
            "Embedding-based deduplication"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG
    }


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return {
        "status": "success",
        "caches": get_cache_stats()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
