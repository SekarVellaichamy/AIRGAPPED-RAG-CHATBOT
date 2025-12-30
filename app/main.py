from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import os
from app.api.routes import router as chat_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.core.config import settings

from app.core.database import init_db
from app.core.logger import setup_logging

# Security Middleware
from app.core.security_middleware import SecurityHeadersMiddleware
from app.core.csrf import CSRFMiddleware
from app.core.rate_limiter import RateLimitMiddleware


class AuthRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect unauthenticated browser requests to login page."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except RuntimeError as e:
            # Handle case where no response is returned (e.g., client disconnected during streaming)
            if "No response returned" in str(e):
                # Return a minimal response to prevent the error from propagating
                from starlette.responses import Response
                return Response(status_code=499)  # Client Closed Request
            raise
        
        # Check if this is a 401 response that needs redirect
        if response.status_code == 401:
            # Check if the response has our custom header indicating browser auth failure
            if response.headers.get("X-Requires-Auth") == "true":
                # Redirect to login page
                return RedirectResponse(url="/login", status_code=302)
        
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce HTTPS when SSL is enabled."""
    
    async def dispatch(self, request: Request, call_next):
        # Check if request is HTTP (not HTTPS)
        if settings.SSL_ENABLED:
            # Check X-Forwarded-Proto header (for reverse proxy) or scheme
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            if request.url.scheme == "http" or forwarded_proto == "http":
                # Build HTTPS URL
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=301)
        
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Logging
    setup_logging()
    # Initialize DB and create default admin
    init_db()
    # Run system check and display status
    from app.core.system_check import print_system_check
    print_system_check()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    # Disable docs in production for security
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Security Middleware Stack (order matters - first added is outermost)
# 0. HTTPS Redirect (enforce HTTPS before any other processing)
if settings.SSL_ENABLED:
    app.add_middleware(HTTPSRedirectMiddleware)

# 1. Security Headers (always applied first)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Rate Limiting (before CSRF to protect against brute force)
app.add_middleware(RateLimitMiddleware)

# 3. CSRF Protection (before auth to validate tokens)
app.add_middleware(CSRFMiddleware)

# 4. Authentication Redirect (innermost - close to routes)
app.add_middleware(AuthRedirectMiddleware)

# Ensure static directory exists
static_dir = "app/static"
os.makedirs(static_dir, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routes
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(admin_router)

# Basic redirect to login if accessing root without auth (optional logic, handled by frontend/middleware usually)
# For now, we keep root as the public chat, but we might want to protect it later.

if __name__ == "__main__":
    import uvicorn
    
    if settings.SSL_ENABLED:
        uvicorn.run(
            app,
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            ssl_keyfile=settings.SSL_KEYFILE,
            ssl_certfile=settings.SSL_CERTFILE
        )
    else:
        uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)

