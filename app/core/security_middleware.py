"""
Security Middleware for FastAPI

Provides comprehensive security headers including:
- Content Security Policy (CSP)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Content Security Policy
        # Allow inline styles/scripts for Bootstrap and our own code
        # Allow fonts from same origin and data URIs
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # Required for inline scripts in templates
            "style-src 'self' 'unsafe-inline'",   # Required for inline styles
            "img-src 'self' data: blob:",         # Allow data URIs and blobs for images
            "font-src 'self' data:",              # Allow fonts from same origin and data URIs
            "connect-src 'self'",                 # Only allow XHR/fetch to same origin
            "frame-ancestors 'none'",             # Prevent embedding in iframes (CSP version of X-Frame-Options)
            "base-uri 'self'",                    # Restrict base tag to same origin
            "form-action 'self'",                 # Restrict form submissions to same origin
            "object-src 'none'",                  # Disable plugins like Flash
            "upgrade-insecure-requests",          # Upgrade HTTP to HTTPS
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # XSS Protection (legacy, but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Cache control for sensitive pages
        if request.url.path.startswith("/admin") or request.url.path == "/login":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
        
        return response
