"""
Lightweight HTTP server for metrics and health endpoints.

Provides a simple HTTP server using stdlib http.server running in a background thread.
Serves:
- GET /metrics -> text/plain metrics in Prometheus format
- GET /healthz -> application/json health status
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from .health import check_health
from .metrics import render_as_text

logger = logging.getLogger(__name__)


class MetricsHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for metrics and health endpoints."""

    def log_message(self, format, *args):
        """Override log_message to use our logger."""
        logger.debug(f"HTTP {self.client_address[0]} - {format % args}")

    def do_GET(self):
        """Handle GET requests."""
        try:
            if self.path == "/metrics":
                self._serve_metrics()
            elif self.path == "/healthz" or self.path == "/health":
                self._serve_health()
            elif self.path == "/" or self.path == "/status":
                self._serve_status()
            else:
                self._serve_404()
        except Exception as e:
            logger.error(f"HTTP handler error: {e}")
            self._serve_error(500, "Internal Server Error")

    def _serve_metrics(self):
        """Serve metrics endpoint."""
        try:
            text = render_as_text()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error serving metrics: {e}")
            self._serve_error(500, "Error generating metrics")

    def _serve_health(self):
        """Serve health endpoint."""
        try:
            health_data = check_health()
            response_json = json.dumps(health_data, indent=2)

            # Set HTTP status based on health status
            status_code = 200
            if health_data.get("status") == "down":
                status_code = 503  # Service Unavailable
            elif health_data.get("status") == "degraded":
                status_code = 200  # Still OK, but degraded

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(response_json.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error serving health: {e}")
            self._serve_error(500, "Error generating health status")

    def _serve_status(self):
        """Serve simple status page."""
        try:
            health_data = check_health()
            status = health_data.get("status", "unknown")

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Bot Status</title>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <h1>Trading Bot Status</h1>
    <p><strong>Status:</strong> {status.upper()}</p>
    <p><strong>Timestamp:</strong> {health_data.get('timestamp', 'N/A')}</p>
    <p><strong>MT5 Connected:</strong> {'✅' if health_data.get('mt5_connected') else '❌'}</p>
    <p><strong>Positions:</strong> {health_data.get('positions_count', 0)}</p>
    <hr>
    <p><a href="/metrics">Metrics</a> | <a href="/healthz">Health JSON</a></p>
</body>
</html>"""

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error serving status page: {e}")
            self._serve_error(500, "Error generating status page")

    def _serve_404(self):
        """Serve 404 Not Found."""
        self._serve_error(404, "Not Found")

    def _serve_error(self, code: int, message: str):
        """Serve an error response."""
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"{code} {message}\n".encode())


class MetricsHTTPServer:
    """HTTP server wrapper for metrics endpoints."""

    def __init__(self, port: int = 9101, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self):
        """Start the HTTP server in a background thread."""
        if self.server:
            logger.warning("HTTP server already started")
            return self.server

        try:
            self.server = HTTPServer((self.host, self.port), MetricsHTTPHandler)
            self.thread = threading.Thread(
                target=self.server.serve_forever, name="MetricsHTTPServer", daemon=True
            )
            self.thread.start()

            logger.info(
                f"Metrics HTTP server started on http://{self.host}:{self.port}"
            )
            logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")
            logger.info(f"  - Health:  http://{self.host}:{self.port}/healthz")
            logger.info(f"  - Status:  http://{self.host}:{self.port}/")

            return self.server

        except Exception as e:
            logger.error(f"Failed to start HTTP server on port {self.port}: {e}")
            self.server = None
            raise

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            logger.info("Stopping metrics HTTP server...")
            self.server.shutdown()
            if self.thread:
                self.thread.join(timeout=5)
            self.server = None
            self.thread = None


# Global server instance
_server: MetricsHTTPServer | None = None


def start_httpd(port: int = 9101, host: str = "0.0.0.0") -> HTTPServer:
    """
    Start the metrics HTTP server.

    Args:
        port: Port to listen on (default: 9101)
        host: Host to bind to (default: 0.0.0.0)

    Returns:
        HTTPServer instance
    """
    global _server

    if _server:
        logger.warning("HTTP server already running")
        return _server.server

    _server = MetricsHTTPServer(port=port, host=host)
    return _server.start()


def stop_httpd():
    """Stop the metrics HTTP server."""
    global _server

    if _server:
        _server.stop()
        _server = None
