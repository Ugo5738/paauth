from typing import Optional
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from auth_service.config import settings

# Default rate limits
DEFAULT_GENERAL_RATE_LIMIT = os.environ.get("GENERAL_RATE_LIMIT", "100/minute")
DEFAULT_LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5/minute")
DEFAULT_REGISTRATION_RATE_LIMIT = os.environ.get("REGISTRATION_RATE_LIMIT", "3/minute")
DEFAULT_PASSWORD_RESET_RATE_LIMIT = os.environ.get("PASSWORD_RESET_RATE_LIMIT", "3/minute")
DEFAULT_TOKEN_RATE_LIMIT = os.environ.get("TOKEN_RATE_LIMIT", "10/minute")

# Create a limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[DEFAULT_GENERAL_RATE_LIMIT],
    strategy="fixed-window",  # "moving-window" is more accurate but more resource-intensive
)

# Define specific rate limits for sensitive endpoints
LOGIN_LIMIT = DEFAULT_LOGIN_RATE_LIMIT
REGISTRATION_LIMIT = DEFAULT_REGISTRATION_RATE_LIMIT
PASSWORD_RESET_LIMIT = DEFAULT_PASSWORD_RESET_RATE_LIMIT
TOKEN_LIMIT = DEFAULT_TOKEN_RATE_LIMIT

# Custom rate limit exceeded handler
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded exceptions"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": exc.retry_after
        },
    )


def setup_rate_limiting(app):
    """Configure rate limiting for the FastAPI application"""
    # Set the app instance on the limiter
    limiter.init_app(app)
    
    # Add rate limiting middleware
    app.add_middleware(SlowAPIMiddleware)
    
    # Add exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
