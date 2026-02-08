# IntelliNews Backend - Setup Guide

## Overview

FastAPI backend with RAG (Retrieval-Augmented Generation), intelligent caching, and multi-source article scraping.

## Prerequisites

- **Python 3.8+**
- **PostgreSQL 14+** with **pgvector** extension
- **OpenAI API Key**
- **Gmail account** (for newsletters)

## Technology Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Relational database
- **pgvector** - Vector similarity search
- **SQLAlchemy** - Python ORM
- **OpenAI API** - Embeddings + GPT
- **arXiv API** - Academic papers
- **feedparser** - RSS feed parsing

## Installation

### macOS

#### 1. Install Python

**Option A: Using Homebrew** (Recommended)
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.11

# Verify installation
python3 --version  # Should show 3.8 or higher
pip3 --version
```

**Option B: Official Installer**
1. Download from https://www.python.org/downloads/
2. Download macOS installer
3. Run the `.pkg` file
4. Verify: `python3 --version`

#### 2. Install PostgreSQL

**Option A: Using Homebrew**
```bash
# Install PostgreSQL
brew install postgresql@14

# Start PostgreSQL service
brew services start postgresql@14

# Verify installation
psql --version
```

**Option B: Using Postgres.app**
1. Download from https://postgresapp.com/
2. Drag to Applications folder
3. Open Postgres.app
4. Click "Initialize" to create default server
5. Add to PATH:
```bash
echo 'export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### 3. Install pgvector Extension

```bash
# Install build tools
brew install git

# Clone pgvector repository
cd ~/Downloads
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# Build and install
make
make install  # May need sudo

# Verify
psql -c "CREATE EXTENSION vector;" -d postgres
```

#### 4. Create Database

```bash
# Create PostgreSQL user (if needed)
createuser -s intellinews_user

# Create database
createdb -O intellinews_user intellinews

# Connect and enable pgvector
psql -d intellinews -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Verify pgvector is installed
psql -d intellinews -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

#### 5. Clone Repository & Setup

```bash
cd ~/Documents  # Or your preferred directory
git clone <repository-url>
cd intellinews/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 6. Configure Environment Variables

```bash
# Create .env file
cp .env.example .env

# Edit .env file
nano .env
```

**Required `.env` configuration**:
```bash
# Database
DATABASE_URL=postgresql://intellinews_user@localhost:5432/intellinews

# OpenAI API Key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-proj-your-key-here

# Email (for newsletters)
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
FROM_EMAIL=your-email@gmail.com

# Security
SECRET_KEY=change-this-to-a-random-string-in-production

# Application
DEBUG=True
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
```

#### 7. Run Database Migrations

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run migrations
alembic upgrade head

# If alembic is not initialized, create initial migration
# alembic revision --autogenerate -m "Initial migration"
# alembic upgrade head
```

#### 8. Create Admin User

```bash
python -c "
from app.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

db = SessionLocal()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

admin = User(
    email='admin@intellinews.com',
    password_hash=pwd_context.hash('admin123'),
    role='admin',
    is_active=True,
    is_verified=True,
    preferences={}
)

db.add(admin)
db.commit()
print('✅ Admin user created: admin@intellinews.com / admin123')
"
```

#### 9. Start Backend Server

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start server
uvicorn app.main:app --reload

# Server should start at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Windows

#### 1. Install Python

**Option A: Using Official Installer** (Recommended)
1. Go to https://www.python.org/downloads/
2. Download "Windows installer (64-bit)"
3. Run installer
4. ☑ Check "Add Python to PATH"
5. Click "Install Now"
6. Verify:
```powershell
python --version  # Should show 3.8+
pip --version
```

**Option B: Using Chocolatey**
```powershell
# Run as Administrator
choco install python

# Verify
python --version
pip --version
```

#### 2. Install PostgreSQL

**Option A: Official Installer** (Recommended)
1. Download from https://www.postgresql.org/download/windows/
2. Run the installer
3. Remember the password you set for the `postgres` user
4. Port: 5432 (default)
5. Verify:
```powershell
psql --version
```

**Option B: Using Chocolatey**
```powershell
# Run as Administrator
choco install postgresql14

# Start PostgreSQL service
net start postgresql-x64-14
```

#### 3. Install pgvector Extension

**Option A: Pre-built Binary** (Easiest)
1. Download from https://github.com/pgvector/pgvector/releases
2. Find "pgvector-windows.zip"
3. Extract to PostgreSQL installation directory:
```powershell
# Default location
C:\Program Files\PostgreSQL\14\
```

**Option B: Build from Source**
1. Install Visual Studio Build Tools
2. Install Git:
```powershell
choco install git
```
3. Clone and build:
```powershell
cd C:\Temp
git clone https://github.com/pgvector/pgvector.git
cd pgvector

# Follow build instructions in README
```

#### 4. Create Database

```powershell
# Open Command Prompt or PowerShell

# Connect to PostgreSQL
psql -U postgres

# In psql prompt:
CREATE USER intellinews_user WITH PASSWORD 'password123';
CREATE DATABASE intellinews OWNER intellinews_user;
\c intellinews
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

#### 5. Clone Repository & Setup

```powershell
cd C:\Users\YourUsername\Documents
git clone <repository-url>
cd intellinews\backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

If you get errors about Visual C++:
```powershell
# Install Visual C++ Build Tools
choco install visualstudio2019buildtools

# OR download from:
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

#### 6. Configure Environment Variables

```powershell
# Copy example .env
copy .env.example .env

# Edit .env file
notepad .env
```

**Required `.env` configuration**:
```bash
# Database
DATABASE_URL=postgresql://intellinews_user:password123@localhost:5432/intellinews

# OpenAI API Key
OPENAI_API_KEY=sk-proj-your-key-here

# Email
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# Security
SECRET_KEY=change-this-to-random-string

# Application
DEBUG=True
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
```

#### 7. Run Database Migrations

```powershell
# Make sure virtual environment is activated
venv\Scripts\activate

# Run migrations
alembic upgrade head
```

#### 8. Create Admin User

```powershell
python -c "from app.database import SessionLocal; from app.models.user import User; from passlib.context import CryptContext; db = SessionLocal(); pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto'); admin = User(email='admin@intellinews.com', password_hash=pwd_context.hash('admin123'), role='admin', is_active=True, is_verified=True, preferences={}); db.add(admin); db.commit(); print('Admin created: admin@intellinews.com / admin123')"
```

#### 9. Start Backend Server

```powershell
# Activate virtual environment
venv\Scripts\activate

# Start server
uvicorn app.main:app --reload

# Server at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Project Structure

```
backend/
├── app/
│   ├── api/                      # API endpoints
│   │   ├── articles.py           # Article discovery, listing
│   │   ├── admin.py              # Admin operations
│   │   ├── auth.py               # Authentication
│   │   └── users.py              # User management
│   ├── models/                   # SQLAlchemy models
│   │   ├── article.py            # Article model
│   │   ├── user.py               # User model
│   │   ├── ranking.py            # Ranking cache model
│   │   └── settings.py           # System settings
│   ├── services/                 # Business logic
│   │   ├── ranking.py            # AI ranking + caching
│   │   ├── retrieval.py          # RAG retrieval
│   │   ├── openai_service.py    # OpenAI API wrapper
│   │   ├── user_scraper.py      # User-specific scraping
│   │   └── deduplication.py     # Duplicate detection
│   ├── scrapers/                 # Article scrapers
│   │   ├── arxiv_scraper.py     # arXiv academic papers
│   │   └── rss_scraper.py       # RSS feed scraper
│   ├── tasks/                    # Background tasks
│   │   ├── scraper_tasks.py     # Scheduled scraping
│   │   └── newsletter_tasks.py  # Email newsletters
│   ├── utils/                    # Utilities
│   ├── database.py               # Database connection
│   ├── config.py                 # Configuration
│   └── main.py                   # FastAPI app
├── alembic/                      # Database migrations
├── requirements.txt              # Python dependencies
└── .env                          # Environment variables
```

## Getting OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Go to API Keys: https://platform.openai.com/api-keys
4. Click "Create new secret key"
5. Copy the key (starts with `sk-proj-...`)
6. Add to `.env` file:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
```

**Pricing**:
- Embeddings (text-embedding-3-large): $0.00013 per 1K tokens
- GPT-4 Turbo: $0.01 per 1K tokens (input), $0.03 per 1K tokens (output)
- With caching: 80-90% cost reduction

## Getting Gmail App Password

1. Go to https://myaccount.google.com/
2. Security → 2-Step Verification (must be enabled)
3. App passwords: https://myaccount.google.com/apppasswords
4. Select app: "Mail"
5. Select device: "Other" → "IntelliNews"
6. Click "Generate"
7. Copy 16-character password (no spaces)
8. Add to `.env`:
```bash
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop  # 16 characters
```

## Database Configuration

### Connection String Format

```bash
postgresql://username:password@host:port/database
```

**Examples**:
```bash
# Local development
DATABASE_URL=postgresql://intellinews_user@localhost:5432/intellinews

# With password
DATABASE_URL=postgresql://intellinews_user:password123@localhost:5432/intellinews

# Remote database
DATABASE_URL=postgresql://user:pass@db.example.com:5432/intellinews
```

### Enable pgvector Extension

```sql
-- Connect to database
psql -d intellinews

-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Testing the Backend

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "development",
  "debug": true
}
```

### API Documentation
Visit: http://localhost:8000/docs

Interactive Swagger UI with all endpoints documented.

### Test Article Scraping

```bash
# Activate virtual environment
source venv/bin/activate  # macOS
venv\Scripts\activate     # Windows

# Run scraper manually
python -c "from app.tasks.scraper_tasks import scrape_and_process_articles; scrape_and_process_articles()"
```

This will:
1. Scrape arXiv for AI papers
2. Scrape RSS feeds (TechCrunch, Wired, etc.)
3. Generate embeddings
4. Save to database

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register user
- `POST /api/auth/signin` - Login
- `POST /api/auth/forgot-password` - Password reset

### Articles
- `POST /api/articles/discover` - Discover ranked articles
- `GET /api/articles/{id}` - Get single article
- `GET /api/articles/` - List articles

### Admin
- `GET /api/admin/users` - List users
- `GET /api/admin/articles` - List articles
- `DELETE /api/admin/articles/{id}` - Delete article
- `GET /api/admin/settings` - Get settings
- `PUT /api/admin/settings` - Update settings

## Troubleshooting

### Issue: "psycopg2" installation fails

**macOS**:
```bash
# Install PostgreSQL development files
brew install postgresql

# Reinstall psycopg2
pip install psycopg2-binary
```

**Windows**:
```powershell
# Use binary version
pip install psycopg2-binary
```

### Issue: "pgvector extension not found"

```sql
-- Connect to database
psql -d intellinews

-- Check available extensions
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- If not found, reinstall pgvector
```

### Issue: "OpenAI API key invalid"

1. Verify key in `.env` file
2. Check for extra spaces or quotes
3. Ensure key starts with `sk-proj-`
4. Verify account has credits at https://platform.openai.com/account/usage

### Issue: Database connection fails

```bash
# Check PostgreSQL is running
# macOS
brew services list | grep postgresql

# Windows
sc query postgresql-x64-14

# Test connection
psql -h localhost -U intellinews_user -d intellinews
```

### Issue: Port 8000 already in use

**macOS**:
```bash
# Find process
lsof -i :8000

# Kill process
kill -9 <PID>

# OR use different port
uvicorn app.main:app --reload --port 8001
```

**Windows**:
```powershell
# Find process
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F

# OR use different port
uvicorn app.main:app --reload --port 8001
```

## Performance Optimization

### Database Indexes

Already configured in models:
- `user_id` (rankings)
- `article_id` (rankings)
- `created_at` (rankings)
- Vector index for embeddings

### Caching Configuration

Edit `app/services/ranking.py`:
```python
class RankingService:
    def __init__(self):
        self.cache_ttl_hours = 1  # Adjust cache TTL
```

### Connection Pooling

Already configured in `app/database.py`:
```python
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=StaticPool  # Change to QueuePool for production
)
```

## Deployment

### Production Checklist

1. **Environment Variables**
```bash
DATABASE_URL=postgresql://user:pass@production-db:5432/intellinews
OPENAI_API_KEY=sk-proj-production-key
SECRET_KEY=long-random-production-secret
DEBUG=False
ENVIRONMENT=production
FRONTEND_URL=https://yourdomain.com
```

2. **Database**
   - Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
   - Enable connection pooling
   - Regular backups

3. **Server**
```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

4. **Nginx Reverse Proxy**
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

5. **SSL Certificate**
```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot --nginx -d api.yourdomain.com
```

## Monitoring

### Logs
```bash
# View logs
tail -f logs/app.log

# View cache effectiveness
tail -f logs/app.log | grep "RankingService"
```

### Database Performance
```sql
-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
```

## Next Steps

1. ✅ Backend is running at http://localhost:8000
2. → Test API at http://localhost:8000/docs
3. → Setup Frontend (see `README_FRONTEND.md`)
4. → Login as admin (admin@intellinews.com / admin123)
5. → Add RSS feeds in admin panel
6. → Run article scraper
7. → Discover articles!

## Support

For issues:
- Check logs in console
- Verify `.env` configuration
- Test database connection
- Check OpenAI API quota

## License

MIT License
