#!/usr/bin/env python3
"""
Dashboard Runner Script

Uvicorn bootstrap for the FastAPI operations dashboard.
Provides a convenient way to start the dashboard with proper configuration.

Usage:
    python scripts/run_dashboard.py [--host HOST] [--port PORT] [--reload]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn

    from config.settings import get_settings
    from dashboard.app import app
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Please install required dependencies:")
    print("  pip install fastapi uvicorn jinja2 python-multipart")
    sys.exit(1)

logger = logging.getLogger(__name__)


def main():
    """Main dashboard runner"""
    parser = argparse.ArgumentParser(description="Run BOT Operations Dashboard")
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind dashboard server (default: from settings)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind dashboard server (default: from settings)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level for uvicorn",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes",
    )

    args = parser.parse_args()

    # Get settings
    try:
        settings = get_settings()
    except Exception as e:
        print(f"Failed to load settings: {e}")
        sys.exit(1)

    # Determine host and port
    host = args.host or settings.observability.dash_host
    port = args.port or settings.observability.dash_port

    # Check if dashboard is enabled
    if not settings.observability.enable_dash:
        print("Dashboard is disabled in settings (ENABLE_DASH=False)")
        print("Set ENABLE_DASH=True to enable the dashboard")
        sys.exit(1)

    print("🚀 Starting BOT Operations Dashboard")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Environment: {settings.environment.value}")
    print(
        f"   Auth Token: {'*' * (len(settings.observability.dash_token) - 4)}{settings.observability.dash_token[-4:]}"
    )
    print(f"   URL: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print()
    print("💡 Authentication:")
    print(f"   Use header: X-DASH-TOKEN: {settings.observability.dash_token}")
    print("   Or add Bearer token to requests")
    print()

    # Configure uvicorn
    uvicorn_config = {
        "app": "dashboard.app:app",
        "host": host,
        "port": port,
        "reload": args.reload,
        "log_level": args.log_level,
        "access_log": True,
        "workers": 1,  # FastAPI with single worker for now
    }

    # Development mode enhancements
    if settings.environment.value == "development" or args.reload:
        uvicorn_config.update(
            {
                "reload": True,
                "reload_dirs": [str(project_root / "dashboard")],
                "log_level": "debug" if args.log_level == "info" else args.log_level,
            }
        )
        print("🔧 Development mode: Auto-reload enabled")

    try:
        # Start the server
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        print(f"❌ Failed to start dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
