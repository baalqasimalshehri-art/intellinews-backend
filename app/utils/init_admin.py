"""
Initialize default admin user on startup
"""

from sqlalchemy import text
from passlib.context import CryptContext
from app.database import engine
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Default admin credentials
DEFAULT_ADMIN_EMAIL = "admin@intellinews.com"
DEFAULT_ADMIN_PASSWORD = "Admin123!"


def create_default_admin():
    """
    Create default admin user if it doesn't exist.

    Credentials:
    Email: admin@intellinews.com
    Password: Admin123!
    """
    try:
        with engine.connect() as conn:
            # Check if admin user already exists
            result = conn.execute(
                text("SELECT id, email, role FROM users WHERE email = :email"),
                {"email": DEFAULT_ADMIN_EMAIL}
            )
            existing_admin = result.first()

            if existing_admin:
                # Admin exists, ensure role is set to admin
                if existing_admin[2] != 'admin':
                    conn.execute(
                        text("UPDATE users SET role = 'admin' WHERE email = :email"),
                        {"email": DEFAULT_ADMIN_EMAIL}
                    )
                    conn.commit()
                    print(f"✅ Updated existing user '{DEFAULT_ADMIN_EMAIL}' to admin role")
                else:
                    print(f"✅ Default admin user already exists: {DEFAULT_ADMIN_EMAIL}")
                return

            # Create new admin user
            hashed_password = pwd_context.hash(DEFAULT_ADMIN_PASSWORD)

            conn.execute(
                text("""
                    INSERT INTO users (email, hashed_password, role, is_active, is_verified, preferences, created_at, updated_at)
                    VALUES (:email, :password, 'admin', true, true, '{}', NOW(), NOW())
                """),
                {
                    "email": DEFAULT_ADMIN_EMAIL,
                    "password": hashed_password
                }
            )
            conn.commit()

            print("=" * 60)
            print("✅ DEFAULT ADMIN USER CREATED!")
            print("=" * 60)
            print(f"📧 Email:    {DEFAULT_ADMIN_EMAIL}")
            print(f"🔑 Password: {DEFAULT_ADMIN_PASSWORD}")
            print("=" * 60)
            print("⚠️  IMPORTANT: Change this password after first login!")
            print("=" * 60)

    except Exception as e:
        print(f"⚠️  Error creating default admin: {e}")


if __name__ == "__main__":
    create_default_admin()
