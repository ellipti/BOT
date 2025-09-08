"""
Dashboard Authentication System (Prompt-28)
JWT-based authentication with roles, refresh tokens, and audit logging.

Features:
- JWT tokens (HS256): Access (15m) + Refresh (7d)
- RBAC: viewer, trader, admin roles
- Password storage: SQLite with bcrypt hashing
- Audit logging: login/logout/violations
- Rate limiting: brute force protection
- Cookie-based auth: HttpOnly, Secure, SameSite=Strict
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from config.settings import get_settings
from infra.secrets import get_secret
from utils.i18n import t  # Монгол хэлний дэмжлэг

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory for simplicity)
_rate_limit_store: dict[str, list[datetime]] = {}

# Valid roles for RBAC
VALID_ROLES = ["viewer", "trader", "admin"]

# Role hierarchy (higher roles inherit lower permissions)
ROLE_HIERARCHY = {
    "admin": ["admin", "trader", "viewer"],
    "trader": ["trader", "viewer"],
    "viewer": ["viewer"],
}


class AuthConfig:
    """Authentication configuration"""

    def __init__(self):
        self.settings = get_settings()
        self._jwt_secret: str | None = None

    @property
    def jwt_secret(self) -> str:
        """Get JWT secret from keyring or environment"""
        if self._jwt_secret is None:
            # Try keyring first, then environment variable
            self._jwt_secret = get_secret("DASH_JWT_SECRET")
            if not self._jwt_secret:
                import os

                self._jwt_secret = os.getenv("DASH_JWT_SECRET")

            if not self._jwt_secret:
                # Generate a development secret if none configured
                dev_secret = f"dev-jwt-secret-{uuid.uuid4().hex[:16]}"
                logger.warning(
                    f"No DASH_JWT_SECRET configured, using dev secret: {dev_secret}"
                )
                self._jwt_secret = dev_secret

        return self._jwt_secret

    @property
    def access_ttl_minutes(self) -> int:
        """Access token TTL in minutes"""
        import os

        return int(os.getenv("DASH_ACCESS_TTL_MIN", "15"))

    @property
    def refresh_ttl_days(self) -> int:
        """Refresh token TTL in days"""
        import os

        return int(os.getenv("DASH_REFRESH_TTL_DAYS", "7"))


# Global auth config instance
_auth_config = AuthConfig()


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def create_access_token(user_id: str, roles: list[str]) -> str:
    """Create JWT access token"""
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=_auth_config.access_ttl_minutes),
        "jti": uuid.uuid4().hex,  # Token ID for tracking
    }

    return jwt.encode(payload, _auth_config.jwt_secret, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token"""
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=_auth_config.refresh_ttl_days),
        "jti": uuid.uuid4().hex,
    }

    return jwt.encode(payload, _auth_config.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, _auth_config.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError as e:
        logger.debug(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )


def check_rate_limit(
    identifier: str, max_attempts: int = 5, window_minutes: int = 15
) -> bool:
    """Check if identifier is rate limited (returns True if allowed)"""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)

    # Clean old attempts
    if identifier in _rate_limit_store:
        _rate_limit_store[identifier] = [
            attempt
            for attempt in _rate_limit_store[identifier]
            if attempt > window_start
        ]
    else:
        _rate_limit_store[identifier] = []

    # Check if rate limit exceeded
    if len(_rate_limit_store[identifier]) >= max_attempts:
        return False

    # Record this attempt
    _rate_limit_store[identifier].append(now)
    return True


def log_audit_event(
    event_type: str, user_id: str = None, details: dict = None, success: bool = True
):
    """Log security audit event"""
    try:
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "success": success,
            "details": details or {},
            "severity": "INFO" if success else "WARNING",
        }

        # Write to audit log file
        audit_file = f"logs/audit-{datetime.now().strftime('%Y')}.jsonl"

        # Ensure logs directory exists
        import os

        os.makedirs("logs", exist_ok=True)

        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry) + "\n")

        logger.info(
            t("auth_login_ok" if success else "auth_login_fail") + f" - {user_id}"
        )

    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")


def get_user_roles(user_id: str, roles_csv: str) -> list[str]:
    """Parse and validate user roles"""
    if not roles_csv:
        return ["viewer"]  # Default role

    roles = [role.strip() for role in roles_csv.split(",") if role.strip()]
    valid_roles = [role for role in roles if role in VALID_ROLES]

    if not valid_roles:
        return ["viewer"]  # Fallback to viewer if no valid roles

    return valid_roles


def check_role_permission(user_roles: list[str], required_roles: list[str]) -> bool:
    """Check if user has any of the required roles (including hierarchy)"""
    if not required_roles:
        return True  # No specific role required

    # Expand user roles with hierarchy
    expanded_roles = set()
    for role in user_roles:
        expanded_roles.update(ROLE_HIERARCHY.get(role, [role]))

    # Check if any required role is satisfied
    return any(role in expanded_roles for role in required_roles)


async def current_user(
    request: Request, required_roles: list[str] | None = None
) -> tuple[str, list[str]]:
    """
    FastAPI dependency to get current authenticated user

    Args:
        request: FastAPI request object
        required_roles: List of roles required to access endpoint

    Returns:
        Tuple of (user_id, user_roles)

    Raises:
        HTTPException: 401 for authentication failure, 403 for authorization failure
    """
    # Get access token from cookies
    access_token = request.cookies.get("access")

    if not access_token:
        log_audit_event("access_denied", details={"reason": "no_token"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Decode and validate token
    try:
        payload = decode_token(access_token)

        # Validate token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user_roles = payload.get("roles", ["viewer"])

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Check role permissions
        if required_roles and not check_role_permission(user_roles, required_roles):
            log_audit_event(
                "role_violation",
                user_id=user_id,
                details={
                    "required_roles": required_roles,
                    "user_roles": user_roles,
                    "endpoint": str(request.url),
                },
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_roles}",
            )

        return user_id, user_roles

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        log_audit_event("auth_error", details={"error": str(e)}, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


# Convenience dependency functions for common role requirements
async def require_viewer(request: Request) -> tuple[str, list[str]]:
    """Require viewer role or higher"""
    return await current_user(request, required_roles=["viewer"])


async def require_trader(request: Request) -> tuple[str, list[str]]:
    """Require trader role or higher"""
    return await current_user(request, required_roles=["trader"])


async def require_admin(request: Request) -> tuple[str, list[str]]:
    """Require admin role"""
    return await current_user(request, required_roles=["admin"])


# Optional dependency for endpoints that work with or without auth
async def optional_user(request: Request) -> tuple[str, list[str]] | None:
    """Optional authentication - returns None if not authenticated"""
    try:
        return await current_user(request)
    except HTTPException:
        return None
