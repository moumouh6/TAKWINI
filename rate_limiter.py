"""
Rate limiting configuration using slowapi.
Limits are applied per IP address.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse

# Create limiter with key function (uses IP address)
limiter = Limiter(key_func=get_remote_address)

# Rate limit configurations
# Auth endpoints - strict limits to prevent brute force
LOGIN_RATE_LIMIT = "5/minute"        # 5 login attempts per minute per IP
REGISTER_RATE_LIMIT = "3/minute"     # 3 registrations per minute per IP

# General API limits
GENERAL_RATE_LIMIT = "100/minute"    # General API usage
STRICT_RATE_LIMIT = "30/minute"      # For write operations


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail if hasattr(exc, 'detail') else 60
        }
    )
