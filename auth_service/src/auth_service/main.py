import logging
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth_service.rate_limiting import limiter, setup_rate_limiting

from auth_service.routers import admin_client_routes
from auth_service.routers import admin_role_routes
from auth_service.routers import admin_permission_routes
from auth_service.routers import admin_role_permission_routes
from auth_service.routers import admin_user_role_routes
from auth_service.routers import admin_client_role_routes
from auth_service.config import settings
from auth_service.schemas import MessageResponse
from auth_service.routers.user_auth_routes import user_auth_router
from auth_service.routers.token_routes import router as token_router

# Configure structured JSON logging
logger = logging.getLogger("auth_service")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '{"timestamp":"%(asctime)s", "level":"%(levelname)s", "name":"%(name)s", "message":"%(message)s"}'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Authentication Service API",
    description="Authentication and Authorization service for managing users, application clients, roles, and permissions.",
    version="1.0.0",
    root_path=settings.root_path,
    openapi_tags=[
        {
            "name": "User Authentication",
            "description": "Operations for user authentication including login, registration, password management, and profile management."
        },
        {
            "name": "Token Acquisition",
            "description": "Operations for obtaining authentication tokens for machine-to-machine (M2M) communication."
        },
        {
            "name": "Admin - App Clients",
            "description": "Administrative operations for managing application clients."
        },
        {
            "name": "Admin - Roles",
            "description": "Administrative operations for managing roles."
        },
        {
            "name": "Admin - Permissions",
            "description": "Administrative operations for managing permissions."
        },
        {
            "name": "Admin - Role Permissions",
            "description": "Administrative operations for assigning permissions to roles."
        },
        {
            "name": "Admin - User Roles",
            "description": "Administrative operations for assigning roles to users."
        },
        {
            "name": "Admin - Client Roles",
            "description": "Administrative operations for assigning roles to application clients."
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True}
)

# Setup rate limiting
setup_rate_limiting(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(user_auth_router)
app.include_router(admin_client_routes.router)
app.include_router(token_router)
app.include_router(admin_role_routes.router, prefix="/auth/admin")
app.include_router(admin_permission_routes.router, prefix="/auth/admin")
app.include_router(admin_role_permission_routes.router, prefix="/auth/admin")
app.include_router(admin_user_role_routes.router, prefix="/auth/admin")
app.include_router(admin_client_role_routes.router, prefix="/auth/admin")

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Rate limit exceeded exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded: {request.client.host} - {request.url.path}")
    # Extract retry seconds from the exception message if available
    # Format is typically '5 per 1 minute'
    retry_seconds = 60  # Default to 60 seconds
    try:
        limit_string = str(exc.detail) if hasattr(exc, 'detail') else str(exc)
        parts = limit_string.split(' per ')
        if len(parts) == 2 and 'minute' in parts[1]:
            # Default retry window is 1 minute
            retry_seconds = 60
        elif len(parts) == 2 and 'hour' in parts[1]:
            # For hourly rate limits
            retry_seconds = 3600
        elif len(parts) == 2 and 'day' in parts[1]:
            # For daily rate limits
            retry_seconds = 86400
    except Exception as e:
        logger.error(f"Error parsing rate limit message: {e}")
        
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "retry_after": retry_seconds
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"ValidationError: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health", response_model=MessageResponse)
async def health():
    logger.info("Health check OK")
    return {"message": "OK"}

# Example error route for HTTPException handler
@app.get("/error")
async def error_example():
    raise HTTPException(status_code=400, detail="Custom error")

# Example echo route to test validation handler
@app.post("/echo", response_model=MessageResponse)
async def echo(item: MessageResponse):
    return item
