"""
Tests for Dashboard Authentication System (Prompt-28)
Tests JWT authentication, RBAC, token refresh, and audit logging.
"""

import json
import logging
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import app
from dashboard.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from dashboard.users import UserStore


class TestAuthCore:
    """Test core authentication functions"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = hash_password(password)

        # Hash should be different from original
        assert hashed != password

        # Verification should work
        assert verify_password(password, hashed)

        # Wrong password should fail
        assert not verify_password("wrong_password", hashed)

    def test_jwt_token_creation(self):
        """Test JWT token creation and validation"""
        user_id = "test_user_123"
        roles = ["viewer", "trader"]

        # Create access token
        access_token = create_access_token(user_id, roles)
        assert isinstance(access_token, str)
        assert len(access_token) > 50  # JWT tokens are quite long

        # Create refresh token
        refresh_token = create_refresh_token(user_id)
        assert isinstance(refresh_token, str)
        assert len(refresh_token) > 50

    @patch("dashboard.auth._auth_config")
    def test_token_expiration(self, mock_config):
        """Test token expiration times"""
        mock_config.access_ttl_minutes = 15
        mock_config.refresh_ttl_days = 7
        mock_config.jwt_secret = "test_secret"

        from jose import jwt

        from dashboard.auth import decode_token

        user_id = "test_user"
        roles = ["viewer"]

        # Create token
        token = create_access_token(user_id, roles)
        payload = jwt.decode(token, "test_secret", algorithms=["HS256"])

        # Check expiration is set correctly
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])

        # Should expire in ~15 minutes
        time_diff = exp_time - iat_time
        assert 14 <= time_diff.total_seconds() / 60 <= 16  # Allow some variance


class TestUserStore:
    """Test user store functionality"""

    def setup_method(self):
        """Set up test database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.user_store = UserStore(db_path=self.temp_db.name)

    def teardown_method(self):
        """Clean up test database"""
        Path(self.temp_db.name).unlink(missing_ok=True)

    def test_create_user(self):
        """Test user creation"""
        email = "test@example.com"
        password = "test_password"
        roles = ["viewer", "trader"]

        user_id = self.user_store.create_user(email, password, roles)

        assert isinstance(user_id, str)
        assert len(user_id) == 36  # UUID length

        # Verify user was created
        user = self.user_store.get_user_by_email(email)
        assert user is not None
        assert user["email"] == email
        assert user["roles"] == roles

    def test_duplicate_email_rejected(self):
        """Test that duplicate emails are rejected"""
        email = "test@example.com"
        password = "test_password"

        # Create first user
        self.user_store.create_user(email, password)

        # Attempt to create duplicate should fail
        with pytest.raises(ValueError, match="already exists"):
            self.user_store.create_user(email, password)

    def test_user_authentication(self):
        """Test user authentication"""
        email = "test@example.com"
        password = "test_password"
        roles = ["trader"]

        # Create user
        user_id = self.user_store.create_user(email, password, roles)

        # Test successful authentication
        user = self.user_store.authenticate_user(email, password)
        assert user is not None
        assert user["id"] == user_id
        assert user["email"] == email
        assert user["roles"] == roles
        assert user["last_login_ts"] is not None

        # Test failed authentication
        assert self.user_store.authenticate_user(email, "wrong_password") is None
        assert self.user_store.authenticate_user("wrong@email.com", password) is None

    def test_role_validation(self):
        """Test role validation"""
        email = "test@example.com"
        password = "test_password"

        # Valid roles should work
        user_id = self.user_store.create_user(
            email, password, ["viewer", "trader", "admin"]
        )
        user = self.user_store.get_user_by_id(user_id)
        assert set(user["roles"]) == {"viewer", "trader", "admin"}

        # Invalid roles should be rejected
        with pytest.raises(ValueError, match="Invalid roles"):
            self.user_store.create_user("test2@example.com", password, ["invalid_role"])

    def test_update_user_roles(self):
        """Test updating user roles"""
        email = "test@example.com"
        password = "test_password"

        user_id = self.user_store.create_user(email, password, ["viewer"])

        # Update roles
        success = self.user_store.update_user_roles(
            user_id, ["viewer", "trader", "admin"]
        )
        assert success

        # Verify update
        user = self.user_store.get_user_by_id(user_id)
        assert set(user["roles"]) == {"viewer", "trader", "admin"}

    def test_user_stats(self):
        """Test user statistics"""
        # Create test users
        self.user_store.create_user("user1@example.com", "password", ["viewer"])
        self.user_store.create_user("user2@example.com", "password", ["trader"])
        self.user_store.create_user("user3@example.com", "password", ["admin"])

        stats = self.user_store.get_stats()

        assert stats["total_users"] == 3
        assert "viewer" in stats["role_counts"]
        assert "trader" in stats["role_counts"]
        assert "admin" in stats["role_counts"]


class TestDashboardAuth:
    """Test dashboard authentication endpoints"""

    def setup_method(self):
        """Set up test client and user store"""
        self.client = TestClient(app)

        # Create temporary user database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        # Patch user store to use temp database
        self.user_store_patcher = patch("dashboard.users._user_store", None)
        self.user_store_patcher.start()

        from dashboard.users import UserStore

        self.user_store = UserStore(db_path=self.temp_db.name)

        # Create test users
        self.viewer_id = self.user_store.create_user(
            "viewer@example.com", "password", ["viewer"]
        )
        self.trader_id = self.user_store.create_user(
            "trader@example.com", "password", ["trader"]
        )
        self.admin_id = self.user_store.create_user(
            "admin@example.com", "password", ["admin"]
        )

    def teardown_method(self):
        """Clean up"""
        self.user_store_patcher.stop()
        Path(self.temp_db.name).unlink(missing_ok=True)

    @patch("dashboard.users.get_user_store")
    def test_login_success(self, mock_get_user_store):
        """Test successful login"""
        mock_get_user_store.return_value = self.user_store

        response = self.client.post(
            "/auth/login", data={"email": "viewer@example.com", "password": "password"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Check cookies are set
        assert "access" in response.cookies
        assert "refresh" in response.cookies

    @patch("dashboard.users.get_user_store")
    def test_login_failure(self, mock_get_user_store):
        """Test failed login"""
        mock_get_user_store.return_value = self.user_store

        response = self.client.post(
            "/auth/login",
            data={"email": "viewer@example.com", "password": "wrong_password"},
        )

        assert response.status_code == 401
        assert "access" not in response.cookies

    @patch("dashboard.users.get_user_store")
    def test_protected_route_access(self, mock_get_user_store):
        """Test access to protected routes with different roles"""
        mock_get_user_store.return_value = self.user_store

        # Login as viewer
        login_response = self.client.post(
            "/auth/login", data={"email": "viewer@example.com", "password": "password"}
        )
        cookies = login_response.cookies

        # Should be able to access overview (requires viewer)
        response = self.client.get("/", cookies=cookies)
        assert response.status_code == 200

        # Should NOT be able to access orders (requires trader)
        response = self.client.get("/orders", cookies=cookies)
        assert response.status_code == 403

        # Should NOT be able to access admin (requires admin)
        response = self.client.get("/admin", cookies=cookies)
        assert response.status_code == 403

    @patch("dashboard.users.get_user_store")
    def test_role_based_access(self, mock_get_user_store):
        """Test role-based access control"""
        mock_get_user_store.return_value = self.user_store

        # Test trader access
        login_response = self.client.post(
            "/auth/login", data={"email": "trader@example.com", "password": "password"}
        )
        trader_cookies = login_response.cookies

        # Trader should access viewer and trader routes
        assert self.client.get("/", cookies=trader_cookies).status_code == 200
        assert self.client.get("/orders", cookies=trader_cookies).status_code == 200

        # But not admin routes
        assert self.client.get("/admin", cookies=trader_cookies).status_code == 403

        # Test admin access
        login_response = self.client.post(
            "/auth/login", data={"email": "admin@example.com", "password": "password"}
        )
        admin_cookies = login_response.cookies

        # Admin should access all routes
        assert self.client.get("/", cookies=admin_cookies).status_code == 200
        assert self.client.get("/orders", cookies=admin_cookies).status_code == 200
        assert self.client.get("/admin", cookies=admin_cookies).status_code == 200

    @patch("dashboard.users.get_user_store")
    def test_token_refresh(self, mock_get_user_store):
        """Test token refresh functionality"""
        mock_get_user_store.return_value = self.user_store

        # Login to get tokens
        login_response = self.client.post(
            "/auth/login", data={"email": "viewer@example.com", "password": "password"}
        )

        original_cookies = login_response.cookies
        original_access = original_cookies["access"]

        # Refresh tokens
        refresh_response = self.client.post("/auth/refresh", cookies=original_cookies)
        assert refresh_response.status_code == 200

        # Should get new tokens
        new_cookies = refresh_response.cookies
        new_access = new_cookies["access"]

        # Access token should be different (rotated)
        assert new_access != original_access

    @patch("dashboard.users.get_user_store")
    def test_logout(self, mock_get_user_store):
        """Test logout functionality"""
        mock_get_user_store.return_value = self.user_store

        # Login first
        login_response = self.client.post(
            "/auth/login", data={"email": "viewer@example.com", "password": "password"}
        )
        cookies = login_response.cookies

        # Verify access works
        assert self.client.get("/", cookies=cookies).status_code == 200

        # Logout
        logout_response = self.client.post("/auth/logout", cookies=cookies)
        assert logout_response.status_code == 200

        # Access should be denied after logout
        response = self.client.get("/", cookies=cookies)
        assert response.status_code == 302  # Redirect to login

    def test_unauthenticated_redirect(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

    def test_public_routes_accessible(self):
        """Test that public routes are accessible without authentication"""
        # These should work without authentication
        assert self.client.get("/login").status_code == 200
        assert self.client.get("/healthz").status_code == 200
        assert self.client.get("/status").status_code == 200


class TestAuditLogging:
    """Test audit logging functionality"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_log_dir = tempfile.mkdtemp()
        self.original_cwd = Path.cwd()

    def teardown_method(self):
        """Clean up"""
        import shutil

        shutil.rmtree(self.temp_log_dir, ignore_errors=True)

    @patch("dashboard.auth.logger")
    def test_audit_logging(self, mock_logger):
        """Test that audit events are logged"""
        with patch("os.makedirs"), patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            from dashboard.auth import log_audit_event

            log_audit_event(
                "test_event",
                user_id="test_user",
                details={"key": "value"},
                success=True,
            )

            # Verify file was opened for append
            mock_open.assert_called_once()
            args, kwargs = mock_open.call_args
            assert "logs/audit-" in args[0]
            assert "a" in args[1]

            # Verify JSON was written
            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]

            # Parse the JSON
            log_entry = json.loads(written_data.strip())
            assert log_entry["event_type"] == "test_event"
            assert log_entry["user_id"] == "test_user"
            assert log_entry["success"] is True
            assert log_entry["details"]["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
