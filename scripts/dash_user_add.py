#!/usr/bin/env python3
"""
Dashboard User Management CLI (Prompt-28)
CLI tool for managing dashboard users and roles.

Usage:
    python scripts/dash_user_add.py user@example.com --roles admin,trader
    python scripts/dash_user_add.py user@example.com --password mypassword --roles viewer
    python scripts/dash_user_add.py --list
    python scripts/dash_user_add.py --stats
"""

import argparse
import getpass
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.auth import log_audit_event
from dashboard.users import get_user_store


def main():
    parser = argparse.ArgumentParser(description="Dashboard User Management CLI")
    parser.add_argument("email", nargs="?", help="User email address")
    parser.add_argument(
        "--password", "-p", help="User password (will prompt if not provided)"
    )
    parser.add_argument(
        "--roles",
        "-r",
        default="viewer",
        help="Comma-separated roles (default: viewer)",
    )
    parser.add_argument("--list", "-l", action="store_true", help="List all users")
    parser.add_argument(
        "--stats", "-s", action="store_true", help="Show user statistics"
    )
    parser.add_argument("--update-roles", "-u", help="Update roles for existing user")
    parser.add_argument(
        "--deactivate", "-d", action="store_true", help="Deactivate user"
    )
    parser.add_argument(
        "--change-password", "-c", action="store_true", help="Change user password"
    )

    args = parser.parse_args()

    user_store = get_user_store()

    try:
        if args.list:
            list_users(user_store)
        elif args.stats:
            show_stats(user_store)
        elif args.email and args.update_roles:
            update_user_roles(user_store, args.email, args.update_roles)
        elif args.email and args.deactivate:
            deactivate_user(user_store, args.email)
        elif args.email and args.change_password:
            change_user_password(user_store, args.email)
        elif args.email:
            create_user(user_store, args.email, args.password, args.roles)
        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def create_user(
    user_store, email: str, password: str = None, roles_str: str = "viewer"
):
    """Create a new user"""
    print(f"Creating user: {email}")

    # Parse roles
    roles = [role.strip() for role in roles_str.split(",") if role.strip()]
    print(f"Roles: {roles}")

    # Get password if not provided
    if not password:
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            raise ValueError("Passwords do not match")

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    # Create user
    user_id = user_store.create_user(email, password, roles)
    print("✅ User created successfully!")
    print(f"   User ID: {user_id}")
    print(f"   Email: {email}")
    print(f"   Roles: {', '.join(roles)}")


def list_users(user_store):
    """List all users"""
    users = user_store.list_users()

    if not users:
        print("No users found.")
        return

    print(f"{'Email':<30} {'Roles':<20} {'Created':<20} {'Last Login':<20}")
    print("-" * 90)

    for user in users:
        from datetime import datetime

        created = datetime.fromtimestamp(user["created_ts"]).strftime("%Y-%m-%d %H:%M")

        if user["last_login_ts"]:
            last_login = datetime.fromtimestamp(user["last_login_ts"]).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            last_login = "Never"

        roles = ", ".join(user["roles"])

        print(f"{user['email']:<30} {roles:<20} {created:<20} {last_login:<20}")


def show_stats(user_store):
    """Show user statistics"""
    stats = user_store.get_stats()

    print("Dashboard User Statistics")
    print("=" * 40)
    print(f"Total Users: {stats['total_users']}")
    print(f"Recent Logins (7 days): {stats['recent_logins']}")
    print(f"Database: {stats['database_path']}")
    print()

    print("Users by Role:")
    for role_csv, count in stats["role_counts"].items():
        print(f"  {role_csv}: {count}")


def update_user_roles(user_store, email: str, roles_str: str):
    """Update user roles"""
    user = user_store.get_user_by_email(email)
    if not user:
        raise ValueError(f"User {email} not found")

    roles = [role.strip() for role in roles_str.split(",") if role.strip()]

    success = user_store.update_user_roles(user["id"], roles)
    if success:
        print(f"✅ Updated roles for {email}: {', '.join(roles)}")
    else:
        raise ValueError("Failed to update user roles")


def deactivate_user(user_store, email: str):
    """Deactivate user"""
    user = user_store.get_user_by_email(email)
    if not user:
        raise ValueError(f"User {email} not found")

    confirm = input(f"Are you sure you want to deactivate {email}? (y/N): ")
    if confirm.lower() != "y":
        print("Cancelled.")
        return

    success = user_store.deactivate_user(user["id"])
    if success:
        print(f"✅ Deactivated user: {email}")
    else:
        raise ValueError("Failed to deactivate user")


def change_user_password(user_store, email: str):
    """Change user password"""
    user = user_store.get_user_by_email(email)
    if not user:
        raise ValueError(f"User {email} not found")

    new_password = getpass.getpass("Enter new password: ")
    password_confirm = getpass.getpass("Confirm new password: ")

    if new_password != password_confirm:
        raise ValueError("Passwords do not match")

    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    success = user_store.change_password(user["id"], new_password)
    if success:
        print(f"✅ Password changed for {email}")
    else:
        raise ValueError("Failed to change password")


if __name__ == "__main__":
    sys.exit(main())
