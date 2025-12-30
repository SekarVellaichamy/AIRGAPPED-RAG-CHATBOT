"""
CSRF Protection for FastAPI

Provides Cross-Site Request Forgery protection using double-submit cookie pattern.
Uses header-based validation to avoid consuming request body in middleware.
"""
import secrets
import hashlib
import hmac
import time
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import HTTPException
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# CSRF token settings
CSRF_TOKEN_LENGTH = 32
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_EXPIRY = 3600 * 4  # 4 hours

# Paths that are exempt from CSRF protection
# Note: All paths are now protected by SameSite=Lax cookies as primary defense
# This middleware adds defense-in-depth for AJAX requests via header validation
CSRF_EXEMPT_PATHS = [
    "/static",
    "/favicon.ico",
    "/docs",
    "/redoc",
    "/openapi.json",
]

# Paths exempt from header check (protected by SameSite cookie instead)
# These are form-based endpoints where we can't easily add headers
CSRF_FORM_EXEMPT_PATHS = [
    "/login",
    "/logout",
    "/chat/new",
    "/chat",  # Chat uses FormData submission
    "/admin/users/create",
    "/admin/users/create-ldap",
    "/admin/files/upload",
    "/admin/tools/convert",
]

# Methods that require CSRF validation
CSRF_REQUIRED_METHODS = ["POST", "PUT", "DELETE", "PATCH"]


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def create_signed_token(token: str, timestamp: Optional[int] = None) -> str:
    """Create a signed CSRF token with timestamp."""
    if timestamp is None:
        timestamp = int(time.time())
    
    # Create signature using HMAC
    message = f"{token}:{timestamp}"
    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    return f"{token}:{timestamp}:{signature}"


def verify_signed_token(signed_token: str) -> bool:
    """Verify a signed CSRF token."""
    try:
        parts = signed_token.split(":")
        if len(parts) != 3:
            return False
        
        token, timestamp_str, signature = parts
        timestamp = int(timestamp_str)
        
        # Check expiry
        if time.time() - timestamp > CSRF_TOKEN_EXPIRY:
            logger.debug("CSRF token expired")
            return False
        
        # Verify signature
        message = f"{token}:{timestamp}"
        expected_signature = hmac.new(
            settings.SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.debug("CSRF signature mismatch")
            return False
        
        return True
    except Exception as e:
        logger.debug(f"CSRF verification error: {e}")
        return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using double-submit cookie pattern.
    
    Defense strategy:
    1. SameSite=Lax cookie attribute (primary defense for all form submissions)
    2. X-CSRF-Token header validation for AJAX requests (defense in depth)
    
    Form-based endpoints are exempted from header check since:
    - SameSite=Lax prevents cross-site form submissions
    - Reading form data in middleware would consume the request body
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        
        # Skip completely exempt paths (static files, etc.)
        if any(path.startswith(exempt) for exempt in CSRF_EXEMPT_PATHS):
            return await call_next(request)
        
        # For state-changing requests, validate CSRF
        if request.method in CSRF_REQUIRED_METHODS:
            # Check if this path uses form submission (exempt from header check)
            is_form_exempt = any(path == exempt or path.startswith(exempt + "/") 
                                  for exempt in CSRF_FORM_EXEMPT_PATHS)
            
            if not is_form_exempt:
                # AJAX requests must include X-CSRF-Token header
                cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                header_token = request.headers.get(CSRF_HEADER_NAME)
                
                if not cookie_token:
                    logger.warning(f"CSRF: Missing cookie for {request.method} {path}")
                    return self._csrf_error_response(request, "Missing CSRF token")
                
                if not header_token:
                    logger.warning(f"CSRF: Missing header for {request.method} {path}")
                    return self._csrf_error_response(request, "Missing CSRF token in request")
                
                # Validate tokens match
                if not hmac.compare_digest(cookie_token, header_token):
                    logger.warning(f"CSRF: Token mismatch for {request.method} {path}")
                    return self._csrf_error_response(request, "CSRF token mismatch")
                
                # Validate token signature
                if not verify_signed_token(cookie_token):
                    logger.warning(f"CSRF: Invalid signature for {request.method} {path}")
                    return self._csrf_error_response(request, "Invalid CSRF token")
        
        # Process request
        response = await call_next(request)
        
        # Set/refresh CSRF cookie for GET requests (and successful POST redirects)
        if request.method == "GET" or (request.method == "POST" and response.status_code in [302, 303]):
            existing_token = request.cookies.get(CSRF_COOKIE_NAME)
            
            # Generate new token if missing or expired
            if not existing_token or not verify_signed_token(existing_token):
                new_token = create_signed_token(generate_csrf_token())
                response.set_cookie(
                    key=CSRF_COOKIE_NAME,
                    value=new_token,
                    max_age=CSRF_TOKEN_EXPIRY,
                    httponly=False,  # Must be readable by JavaScript for AJAX
                    samesite="lax",
                    secure=settings.SECURE_COOKIES,
                    path="/"
                )
        
        return response
    
    def _csrf_error_response(self, request: Request, message: str) -> Response:
        """Return appropriate CSRF error response based on request type."""
        accept = request.headers.get("accept", "")
        
        if "application/json" in accept:
            return JSONResponse(
                status_code=403,
                content={"detail": message}
            )
        else:
            # For HTML requests, redirect to login with error
            from starlette.responses import RedirectResponse
            return RedirectResponse(
                url="/login?error=Session expired, please try again",
                status_code=302
            )


def get_csrf_token(request: Request) -> str:
    """Get CSRF token from request cookies for use in templates."""
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token or not verify_signed_token(token):
        token = create_signed_token(generate_csrf_token())
    return token

