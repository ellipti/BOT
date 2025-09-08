"""
FastAPI-based Operations Dashboard with JWT Authentication (Prompt-28)

Features:
- JWT-based authentication with access/refresh tokens
- RBAC: viewer, trader, admin roles
- Cookie-based auth: HttpOnly, Secure, SameSite=Strict
- Rate limiting and audit logging
- Password storage with bcrypt hashing

Provides web interface for:
- System health monitoring
- Order book visualization  
- Metrics and KPIs
- Chart visualization
- User management (admin only)
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import get_settings
from dashboard.auth import (
    create_access_token, create_refresh_token, decode_token, check_rate_limit,
    log_audit_event, require_viewer, require_trader, require_admin, optional_user
)
from dashboard.deps import DashboardDataProvider, get_dashboard_provider
from dashboard.users import get_user_store

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BOT Operations Dashboard",
    description="Real-time trading bot monitoring and operations dashboard with JWT authentication",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup templates and static files
templates = Jinja2Templates(directory="dashboard/templates")
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Store JWT secret in app state for dependency injection
@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    app.state.jwt_secret = settings.observability.dash_jwt_secret
    
    # Add template filters
    def timestamp_to_date(timestamp):
        if timestamp:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
        return "Never"
    
    templates.env.filters['timestamp_to_date'] = timestamp_to_date


# ================================
# Route Protection and Redirects
# ================================

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Global authentication middleware"""
    # Public routes that don't require authentication
    public_paths = ["/login", "/healthz", "/status", "/docs", "/redoc", "/openapi.json"]
    legacy_paths = ["/legacy/"]
    
    # Check if this is a public route
    if (request.url.path in public_paths or 
        any(request.url.path.startswith(path) for path in legacy_paths) or
        request.url.path.startswith("/static/")):
        return await call_next(request)
    
    # For all other routes, check authentication
    access_token = request.cookies.get("access")
    
    if not access_token:
        # Redirect to login for browser requests
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        else:
            # Return 401 for API requests
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"}
            )
    
    # Proceed with the request
    return await call_next(request)



# ================================
# Authentication Routes (Prompt-28)
# ================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Login"}
    )


@app.post("/auth/login")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
):
    """Login endpoint - authenticate user and set JWT cookies"""
    client_ip = request.client.host
    
    # Rate limiting check
    if not check_rate_limit(f"login:{client_ip}", max_attempts=5, window_minutes=15):
        log_audit_event("login_rate_limited", details={"ip": client_ip, "email": email}, success=False)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    # Authenticate user
    user_store = get_user_store()
    user = user_store.authenticate_user(email, password)
    
    if not user:
        # Still count this against rate limit
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create tokens
    access_token = create_access_token(user["id"], user["roles"])
    refresh_token = create_refresh_token(user["id"])
    
    # Set secure cookies
    settings = get_settings()
    is_secure = settings.environment != "development"
    
    response.set_cookie(
        key="access",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.observability.dash_access_ttl_min * 60
    )
    
    response.set_cookie(
        key="refresh",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.observability.dash_refresh_ttl_days * 24 * 60 * 60
    )
    
    log_audit_event("login_success", user_id=user["id"], details={"email": email, "ip": client_ip})
    
    return {"status": "success", "message": "Login successful", "redirect": "/"}


@app.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response):
    """Refresh access token using refresh token"""
    refresh_token = request.cookies.get("refresh")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    try:
        # Decode refresh token
        payload = decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user to verify still active and get current roles
        user_store = get_user_store()
        user = user_store.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new tokens (token rotation)
        new_access_token = create_access_token(user_id, user["roles"])
        new_refresh_token = create_refresh_token(user_id)
        
        # Set new cookies
        settings = get_settings()
        is_secure = settings.environment != "development"
        
        response.set_cookie(
            key="access",
            value=new_access_token,
            httponly=True,
            secure=is_secure,
            samesite="strict",
            max_age=settings.observability.dash_access_ttl_min * 60
        )
        
        response.set_cookie(
            key="refresh",
            value=new_refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="strict",
            max_age=settings.observability.dash_refresh_ttl_days * 24 * 60 * 60
        )
        
        log_audit_event("token_refresh", user_id=user_id)
        
        return {"status": "success", "message": "Token refreshed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout endpoint - clear JWT cookies"""
    # Get user info for audit log
    user_info = await optional_user(request)
    user_id = user_info[0] if user_info else None
    
    # Clear cookies
    response.delete_cookie(key="access", httponly=True, samesite="strict")
    response.delete_cookie(key="refresh", httponly=True, samesite="strict")
    
    log_audit_event("logout", user_id=user_id)
    
    return {"status": "success", "message": "Logged out successfully", "redirect": "/login"}


# ================================
# Protected Dashboard Routes
# ================================


@app.get("/", response_class=HTMLResponse)
async def dashboard_overview(
    request: Request,
    user_info = Depends(require_viewer),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Main dashboard overview page (requires viewer role)"""
    user_id, user_roles = user_info
    
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
                "user_id": user_id,
                "user_roles": user_roles,
            },
        )

    except Exception as e:
        logger.error(f"Dashboard overview error: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}") from e


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    status_filter: str | None = None,
    user_info = Depends(require_trader),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Orders management page (requires trader role)"""
    user_id, user_roles = user_info
    
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
                "user_id": user_id,
                "user_roles": user_roles,
            },
        )

    except Exception as e:
        logger.error(f"Orders page error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Orders page error: {str(e)}"
        ) from e


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    user_info = Depends(require_admin),
):
    """Admin page (requires admin role)"""
    user_id, user_roles = user_info
    
    try:
        user_store = get_user_store()
        users = user_store.list_users()
        stats = user_store.get_stats()

        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "title": "Administration",
                "users": users,
                "stats": stats,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": user_id,
                "user_roles": user_roles,
            },
        )

    except Exception as e:
        logger.error(f"Admin page error: {e}")
        raise HTTPException(status_code=500, detail=f"Admin error: {str(e)}") from e


@app.get("/charts/{symbol}", response_class=HTMLResponse)
async def charts_page(
    symbol: str,
    request: Request,
    limit: int = 100,
    user_info = Depends(require_viewer),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Chart visualization page for symbol (requires viewer role)"""
    user_id, user_roles = user_info
    
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
                "user_id": user_id,
                "user_roles": user_roles,
            },
        )

    except Exception as e:
        logger.error(f"Charts page error: {e}")
        raise HTTPException(status_code=500, detail=f"Charts error: {str(e)}") from e


# ================================
# API Endpoints for HTMX and JSON responses
# ================================

@app.get("/api/health")
async def api_health(
    user_info = Depends(require_viewer),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for health status (requires viewer role)"""
    return provider.get_health_status()


@app.get("/api/orders")
async def api_orders(
    status_filter: str | None = None,
    user_info = Depends(require_trader),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for orders data (requires trader role)"""
    return {
        "orders": provider.get_orders_by_status(status_filter),
        "summary": provider.get_orders_summary(),
    }


@app.get("/api/metrics")
async def api_metrics(
    user_info = Depends(require_viewer),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for metrics data (requires viewer role)"""
    return provider.get_metrics_data()


@app.get("/api/charts/{symbol}")
async def api_chart_data(
    symbol: str,
    limit: int = 100,
    user_info = Depends(require_viewer),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """API endpoint for chart data (requires viewer role)"""
    return provider.get_chart_data(symbol.upper(), limit)


@app.get("/api/admin/users")
async def api_admin_users(
    user_info = Depends(require_admin),
):
    """API endpoint for user management (requires admin role)"""
    user_store = get_user_store()
    return {
        "users": user_store.list_users(),
        "stats": user_store.get_stats()
    }


# ================================
# Legacy token support (X-DASH-TOKEN header)
# ================================

async def verify_legacy_token(request: Request) -> bool:
    """Legacy authentication for backward compatibility"""
    settings = get_settings()
    token = request.headers.get("X-DASH-TOKEN")
    
    if token == settings.observability.dash_token:
        return True
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-DASH-TOKEN",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/legacy/health")
async def legacy_health(
    request: Request,
    authenticated: bool = Depends(verify_legacy_token),
    provider: DashboardDataProvider = Depends(get_dashboard_provider),
):
    """Legacy health endpoint with X-DASH-TOKEN authentication"""
    return provider.get_health_status()


# ================================
# Public endpoints (no authentication)
# ================================


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
