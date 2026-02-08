"""
Script to promote a user to admin role
Usage: python app/scripts/make_admin.py <email>
"""

import sys
from sqlalchemy import text
from app.database import engine


def make_admin(email: str):
    """Promote user to admin role"""
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(
            text("SELECT id, email, role FROM users WHERE email = :email"),
            {"email": email}
        )
        user = result.first()

        if not user:
            print(f"❌ User with email '{email}' not found!")
            return False

        # Update role to admin
        conn.execute(
            text("UPDATE users SET role = 'admin' WHERE email = :email"),
            {"email": email}
        )
        conn.commit()

        print(f"✅ User '{email}' promoted to admin!")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app/scripts/make_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    make_admin(email)
