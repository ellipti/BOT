"""
FastAPI-based Operations Dashboard

Provides web interface for:
- System health monitoring
- Order book visualization
- Metrics and KPIs
- Chart visualization
- Authentication via X-DASH-TOKEN header
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import get_settings
from dashboard.deps import DashboardDataProvider, get_dashboard_provider

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BOT Operations Dashboard",
    description="Real-time trading bot monitoring and operations dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup templates and static files
templates = Jinja2Templates(directory="dashboard/templates")
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Authentication
security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
) -> bool:
    """Verify dashboard authentication token"""
    settings = get_settings()

    # Check header token first (X-DASH-TOKEN)
    token = request.headers.get("X-DASH-TOKEN") if request else None

    # Fallback to Bearer token
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token != settings.observability.dash_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


@app.get("/", response_class=HTMLResponse)
async def dashboard_overview(
    request: Request,
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Main dashboard overview page"""
    try:
        # Gather all dashboard data
        health_status = provider.get_health_status()
        orders_summary = provider.get_orders_summary()
        metrics_data = provider.get_metrics_data()

        # Calculate KPIs
        kpis = {
            "total_orders": orders_summary.get("total_orders", 0),
            "today_pnl": orders_summary.get("today_pnl", 0.0),
            "filled_orders": orders_summary.get("status_counts", {}).get("FILLED", 0),
            "pending_orders": orders_summary.get("status_counts", {}).get("PENDING", 0),
            "system_status": health_status.get("status", "unknown"),
            "metrics_count": metrics_data.get("total_metrics", 0),
        }

        return templates.TemplateResponse(
            "overview.html",
            {
                "request": request,
                "title": "Dashboard Overview",
                "health_status": health_status,
                "orders_summary": orders_summary,
                "kpis": kpis,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    except Exception as e:
        logger.error(f"Dashboard overview error: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}") from e


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    status_filter: str | None = None,
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Orders management page"""
    try:
        orders = provider.get_orders_by_status(status_filter)
        status_counts = provider.get_orders_summary().get("status_counts", {})

        return templates.TemplateResponse(
            "orders.html",
            {
                "request": request,
                "title": f"Orders {f'- {status_filter}' if status_filter else ''}",
                "orders": orders,
                "status_counts": status_counts,
                "current_filter": status_filter,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    except Exception as e:
        logger.error(f"Orders page error: {e}")
        raise HTTPException(status_code=500, detail=f"Orders page error: {str(e)}") from e


@app.get("/charts/{symbol}", response_class=HTMLResponse)
async def charts_page(
    symbol: str,
    request: Request,
    limit: int = 100,
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Chart visualization page for symbol"""
    try:
        chart_data = provider.get_chart_data(symbol.upper(), limit)

        return templates.TemplateResponse(
            "charts.html",
            {
                "request": request,
                "title": f"Chart - {symbol.upper()}",
                "symbol": symbol.upper(),
                "chart_data": chart_data,
                "limit": limit,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    except Exception as e:
        logger.error(f"Charts page error: {e}")
        raise HTTPException(status_code=500, detail=f"Charts error: {str(e)}") from e


# API Endpoints for HTMX and JSON responses
@app.get("/api/health")
async def api_health(
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for health status"""
    return provider.get_health_status()


@app.get("/api/orders")
async def api_orders(
    status_filter: str | None = None,
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for orders data"""
    return {
        "orders": provider.get_orders_by_status(status_filter),
        "summary": provider.get_orders_summary(),
    }


@app.get("/api/metrics")
async def api_metrics(
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for metrics data"""
    return provider.get_metrics_data()


@app.get("/api/charts/{symbol}")
async def api_chart_data(
    symbol: str,
    limit: int = 100,
    authenticated: bool = Depends(verify_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for chart data"""
    return provider.get_chart_data(symbol.upper(), limit)


# Health endpoint (no auth required)
@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "dashboard",
        "timestamp": datetime.now().isoformat(),
    }


# Status endpoint (no auth required)
@app.get("/status")
async def status_endpoint():
    """Service status endpoint"""
    settings = get_settings()
    return {
        "service": "BOT Operations Dashboard",
        "version": "1.0.0",
        "environment": settings.environment.value,
        "auth_enabled": True,
        "timestamp": datetime.now().isoformat(),
    }


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return templates.TemplateResponse(
        "404.html", {"request": request, "title": "Page Not Found"}, status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 handler"""
    logger.error(f"Server error: {exc}")
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "title": "Server Error", "error": str(exc)},
        status_code=500,
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "dashboard.app:app",
        host=settings.observability.dash_host,
        port=settings.observability.dash_port,
        reload=settings.environment == "development",
    )
