"""
Rate Limiter for FastAPI

Simple in-memory rate limiting to prevent brute force and abuse.
"""
import time
from collections import defaultdict
from typing import Dict, Tuple, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory sliding window rate limiter."""
    
    def __init__(self):
        # Structure: {key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
    
    def _clean_old_requests(self, key: str, window_seconds: int):
        """Remove requests outside the current window."""
        cutoff = time.time() - window_seconds
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key]
            if ts > cutoff
        ]
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        
        Returns: (is_allowed, remaining_requests)
        """
        current_time = time.time()
        
        # Clean old requests
        self._clean_old_requests(key, window_seconds)
        
        # Count requests in current window
        total_requests = sum(count for _, count in self._requests[key])
        
        if total_requests >= max_requests:
            return False, 0
        
        # Add current request
        self._requests[key].append((current_time, 1))
        
        return True, max_requests - total_requests - 1
    
    def get_retry_after(self, key: str, window_seconds: int) -> int:
        """Get seconds until oldest request expires from window."""
        if not self._requests[key]:
            return 0
        
        oldest = min(ts for ts, _ in self._requests[key])
        retry_after = int(oldest + window_seconds - time.time())
        return max(0, retry_after)


# Global rate limiter instance
rate_limiter = RateLimiter()

# Rate limit configurations
RATE_LIMITS = {
    # Path pattern: (max_requests, window_seconds)
    "/login": (5, 60),           # 5 login attempts per minute per IP
    "/admin/users/create": (10, 60),  # 10 user creates per minute
    "/admin/files/upload": (10, 60),  # 10 uploads per minute
    "/chat": (60, 60),           # 60 chat messages per minute
}


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded headers (if behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next):
        # Only rate limit specific paths
        path = request.url.path
        
        # Find matching rate limit config
        limit_config = None
        for pattern, config in RATE_LIMITS.items():
            if path == pattern or path.startswith(pattern + "/"):
                limit_config = config
                break
        
        if limit_config and request.method in ["POST", "PUT", "DELETE"]:
            max_requests, window_seconds = limit_config
            
            # Create rate limit key based on IP and path
            client_ip = get_client_ip(request)
            rate_key = f"{client_ip}:{path}"
            
            is_allowed, remaining = rate_limiter.is_allowed(
                rate_key, max_requests, window_seconds
            )
            
            if not is_allowed:
                retry_after = rate_limiter.get_retry_after(rate_key, window_seconds)
                logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please try again later.",
                        "retry_after": retry_after
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after)
                    }
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
        
        return await call_next(request)
