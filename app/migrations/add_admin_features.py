"""
Migration script to add admin features:
1. Add 'role' column to users table
2. Create newsletter_logs table
3. Create system_settings table
"""

from sqlalchemy import text
from app.database import engine


def upgrade():
    """Apply migration"""
    with engine.connect() as conn:
        # Add role column to users table
        print("Adding role column to users table...")
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user' NOT NULL;
        """))
        conn.commit()

        # Create newsletter_logs table
        print("Creating newsletter_logs table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS newsletter_logs (
                id SERIAL PRIMARY KEY,
                subject VARCHAR(500) NOT NULL,
                recipients INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'Completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()

        # Create system_settings table
        print("Creating system_settings table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(key);
        """))
        conn.commit()

        print("Migration completed successfully!")


def downgrade():
    """Rollback migration"""
    with engine.connect() as conn:
        print("Rolling back admin features migration...")

        # Drop tables
        conn.execute(text("DROP TABLE IF EXISTS system_settings;"))
        conn.execute(text("DROP TABLE IF EXISTS newsletter_logs;"))

        # Remove role column
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS role;"))

        conn.commit()
        print("Rollback completed!")


if __name__ == "__main__":
    print("Running admin features migration...")
    upgrade()
