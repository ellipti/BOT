"""
Dashboard User Store (Prompt-28)
SQLite-based user management with bcrypt password hashing.

Database: infra/dash_users.sqlite
Schema: users(id, email, pwd_hash, roles_csv, created_ts, last_login_ts)
"""

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dashboard.auth import (
    get_user_roles,
    hash_password,
    log_audit_event,
    verify_password,
)

logger = logging.getLogger(__name__)

# Database path
DB_PATH = "infra/dash_users.sqlite"


class UserStore:
    """SQLite-based user store with bcrypt password hashing"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database and table exist"""
        # Create directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    pwd_hash TEXT NOT NULL,
                    roles_csv TEXT DEFAULT 'viewer',
                    created_ts INTEGER NOT NULL,
                    last_login_ts INTEGER DEFAULT NULL,
                    active INTEGER DEFAULT 1
                )
            """
            )

            # Create index on email for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like row access
        try:
            yield conn
        finally:
            conn.close()

    def create_user(self, email: str, password: str, roles: list[str] = None) -> str:
        """
        Create new user with hashed password

        Args:
            email: User email (must be unique)
            password: Plain text password (will be hashed)
            roles: List of roles (defaults to ['viewer'])

        Returns:
            User ID

        Raises:
            ValueError: If email already exists or invalid data
        """
        if not email or not password:
            raise ValueError("Email and password are required")

        if roles is None:
            roles = ["viewer"]

        # Validate roles
        valid_roles = ["viewer", "trader", "admin"]
        invalid_roles = [r for r in roles if r not in valid_roles]
        if invalid_roles:
            raise ValueError(f"Invalid roles: {invalid_roles}. Valid: {valid_roles}")

        user_id = str(uuid.uuid4())
        pwd_hash = hash_password(password)
        roles_csv = ",".join(roles)
        created_ts = int(datetime.utcnow().timestamp())

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (id, email, pwd_hash, roles_csv, created_ts)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (user_id, email.lower().strip(), pwd_hash, roles_csv, created_ts),
                )
                conn.commit()

                log_audit_event(
                    "user_created",
                    user_id=user_id,
                    details={"email": email, "roles": roles},
                )
                logger.info(f"Created user {email} with roles {roles}")

                return user_id

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"User with email {email} already exists")
            raise ValueError(f"Database error: {e}")

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        """
        Authenticate user by email and password

        Args:
            email: User email
            password: Plain text password

        Returns:
            User dict if authentication successful, None otherwise
        """
        if not email or not password:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, pwd_hash, roles_csv, created_ts, last_login_ts
                FROM users
                WHERE email = ? AND active = 1
            """,
                (email.lower().strip(),),
            )

            row = cursor.fetchone()
            if not row:
                log_audit_event(
                    "login_failed",
                    details={"email": email, "reason": "user_not_found"},
                    success=False,
                )
                return None

            # Verify password
            if not verify_password(password, row["pwd_hash"]):
                log_audit_event(
                    "login_failed",
                    user_id=row["id"],
                    details={"email": email, "reason": "invalid_password"},
                    success=False,
                )
                return None

            # Update last login timestamp
            user_id = row["id"]
            login_ts = int(datetime.utcnow().timestamp())
            cursor.execute(
                """
                UPDATE users SET last_login_ts = ? WHERE id = ?
            """,
                (login_ts, user_id),
            )
            conn.commit()

            user_data = {
                "id": row["id"],
                "email": row["email"],
                "roles": get_user_roles(user_id, row["roles_csv"]),
                "created_ts": row["created_ts"],
                "last_login_ts": login_ts,
            }

            log_audit_event("login_success", user_id=user_id, details={"email": email})
            return user_data

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, roles_csv, created_ts, last_login_ts
                FROM users
                WHERE id = ? AND active = 1
            """,
                (user_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row["id"],
                "email": row["email"],
                "roles": get_user_roles(user_id, row["roles_csv"]),
                "created_ts": row["created_ts"],
                "last_login_ts": row["last_login_ts"],
            }

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user by email"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, roles_csv, created_ts, last_login_ts
                FROM users
                WHERE email = ? AND active = 1
            """,
                (email.lower().strip(),),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row["id"],
                "email": row["email"],
                "roles": get_user_roles(row["id"], row["roles_csv"]),
                "created_ts": row["created_ts"],
                "last_login_ts": row["last_login_ts"],
            }

    def list_users(self) -> list[dict[str, Any]]:
        """List all active users"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, roles_csv, created_ts, last_login_ts
                FROM users
                WHERE active = 1
                ORDER BY created_ts DESC
            """
            )

            return [
                {
                    "id": row["id"],
                    "email": row["email"],
                    "roles": get_user_roles(row["id"], row["roles_csv"]),
                    "created_ts": row["created_ts"],
                    "last_login_ts": row["last_login_ts"],
                }
                for row in cursor.fetchall()
            ]

    def update_user_roles(self, user_id: str, roles: list[str]) -> bool:
        """Update user roles"""
        # Validate roles
        valid_roles = ["viewer", "trader", "admin"]
        invalid_roles = [r for r in roles if r not in valid_roles]
        if invalid_roles:
            raise ValueError(f"Invalid roles: {invalid_roles}. Valid: {valid_roles}")

        roles_csv = ",".join(roles)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users SET roles_csv = ? WHERE id = ? AND active = 1
            """,
                (roles_csv, user_id),
            )

            if cursor.rowcount > 0:
                conn.commit()
                log_audit_event(
                    "user_roles_updated", user_id=user_id, details={"new_roles": roles}
                )
                return True

            return False

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Change user password"""
        if not new_password:
            raise ValueError("Password cannot be empty")

        pwd_hash = hash_password(new_password)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users SET pwd_hash = ? WHERE id = ? AND active = 1
            """,
                (pwd_hash, user_id),
            )

            if cursor.rowcount > 0:
                conn.commit()
                log_audit_event("password_changed", user_id=user_id)
                return True

            return False

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user (soft delete)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users SET active = 0 WHERE id = ?
            """,
                (user_id,),
            )

            if cursor.rowcount > 0:
                conn.commit()
                log_audit_event("user_deactivated", user_id=user_id)
                return True

            return False

    def get_stats(self) -> dict[str, Any]:
        """Get user statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total users
            cursor.execute("SELECT COUNT(*) FROM users WHERE active = 1")
            total_users = cursor.fetchone()[0]

            # Users by role
            cursor.execute(
                """
                SELECT roles_csv, COUNT(*)
                FROM users
                WHERE active = 1
                GROUP BY roles_csv
            """
            )
            role_counts = dict(cursor.fetchall())

            # Recent logins (last 7 days)
            week_ago = int((datetime.utcnow().timestamp()) - (7 * 24 * 3600))
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE active = 1 AND last_login_ts >= ?
            """,
                (week_ago,),
            )
            recent_logins = cursor.fetchone()[0]

            return {
                "total_users": total_users,
                "role_counts": role_counts,
                "recent_logins": recent_logins,
                "database_path": self.db_path,
            }


# Global user store instance
_user_store: UserStore | None = None


def get_user_store() -> UserStore:
    """Get global user store instance"""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
