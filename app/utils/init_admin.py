"""
Initialize the administrator account on startup.

Credentials are read from the environment, never from source code:
  ADMIN_EMAIL     (default: admin@intellinews.com)
  ADMIN_PASSWORD  (required to create the account or to reset its password)

If ADMIN_PASSWORD is set and the stored password differs, the stored
password is replaced, so the administrator password can be rotated from
the hosting settings without signing in.
"""

from sqlalchemy import text
from passlib.context import CryptContext
from app.database import engine
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_default_admin():
    """Create or update the administrator account from environment settings."""
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, email, role, hashed_password FROM users WHERE email = :email"),
                {"email": admin_email}
            )
            existing_admin = result.first()

            if existing_admin:
                if existing_admin[2] != 'admin':
                    conn.execute(
                        text("UPDATE users SET role = 'admin' WHERE email = :email"),
                        {"email": admin_email}
                    )
                    print(f"[Admin] Updated '{admin_email}' to admin role")

                if admin_password and not pwd_context.verify(admin_password, existing_admin[3] or ""):
                    conn.execute(
                        text("UPDATE users SET hashed_password = :password, updated_at = NOW() WHERE email = :email"),
                        {"email": admin_email, "password": pwd_context.hash(admin_password)}
                    )
                    print(f"[Admin] Administrator password updated from ADMIN_PASSWORD for '{admin_email}'")

                conn.commit()
                return

            if not admin_password:
                print("[Admin] ADMIN_PASSWORD is not set; no administrator account was created.")
                return

            conn.execute(
                text("""
                    INSERT INTO users (email, hashed_password, role, is_active, is_verified, preferences, created_at, updated_at)
                    VALUES (:email, :password, 'admin', true, true, '{}', NOW(), NOW())
                """),
                {"email": admin_email, "password": pwd_context.hash(admin_password)}
            )
            conn.commit()
            print(f"[Admin] Administrator account created for '{admin_email}'")

    except Exception as e:
        print(f"[Admin] Error initializing administrator account: {e}")


if __name__ == "__main__":
    create_default_admin()
