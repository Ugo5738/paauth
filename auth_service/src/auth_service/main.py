import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient

from auth_service.rate_limiting import limiter, setup_rate_limiting
from auth_service.bootstrap import bootstrap_admin_and_rbac
from auth_service.db import get_db
from auth_service.supabase_client import get_supabase_client
from auth_service.logging_config import setup_logging, LoggingMiddleware, logger

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run bootstrap process to create admin user and RBAC components
    logger.info("Starting application bootstrap process")
    
    # Get database session and Supabase client
    db_generator = get_db()
    try:
        db = await anext(db_generator)
        supabase = get_supabase_client()
        
        # Run bootstrap process
        success = await bootstrap_admin_and_rbac(db, supabase)
        if success:
            logger.info("Bootstrap process completed successfully")
        else:
            logger.warning("Bootstrap process completed with errors")
    except Exception as e:
        logger.error(f"Error during bootstrap process: {str(e)}")
    finally:
        try:
            # Ensure we close the DB session if it was opened
            if 'db_generator' in locals():
                await db_generator.aclose()
        except Exception as e:
            logger.error(f"Error closing DB session: {str(e)}")
    
    logger.info("Application startup complete")
    yield
    # Shutdown: Cleanup resources if needed
    logger.info("Application shutting down")

app = FastAPI(
    title="Authentication Service API",
    description="Authentication and Authorization service for managing users, application clients, roles, and permissions.",
    version="1.0.0",
    root_path=settings.root_path,
    lifespan=lifespan,
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

# Setup logging configuration
setup_logging(app)

# Setup rate limiting
setup_rate_limiting(app)

# Add logging middleware (after request_id middleware which is added in setup_logging)
app.add_middleware(LoggingMiddleware)

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


@app.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    supabase: AsyncClient = Depends(get_supabase_client)
):
    """
    Health check endpoint that verifies the service and its dependencies are working.
    Returns application status, version, and component health information.
    """
    import datetime
    
    # Initialize response object
    response = {
        "status": "ok",
        "version": app.version,
        "environment": str(settings.environment),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "components": {
            "api": {
                "status": "ok"
            }
        }
    }
    
    # Check database connectivity
    try:
        # Simple query to verify database connection
        await db.execute("SELECT 1")
        response["components"]["database"] = {
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Health check - Database error: {str(e)}")
        response["components"]["database"] = {
            "status": "error",
            "message": "Database connection failed"
        }
        response["status"] = "degraded"
    
    # Check Supabase connectivity
    try:
        # Simple request to verify Supabase connection
        await supabase.auth.get_user("invalid-token-just-for-testing")
    except Exception as e:
        # This will fail with an auth error, which is expected
        # We just want to ensure we can reach Supabase
        if "401" in str(e) or "invalid token" in str(e).lower():
            response["components"]["supabase"] = {
                "status": "ok"
            }
        else:
            logger.error(f"Health check - Supabase error: {str(e)}")
            response["components"]["supabase"] = {
                "status": "error",
                "message": "Supabase connection failed"
            }
            response["status"] = "degraded"
    
    # Set appropriate status code based on overall status
    status_code = 200 if response["status"] == "ok" else 503
    
    logger.info(f"Health check completed with status: {response['status']}")
    return JSONResponse(content=response, status_code=status_code)

# Example error route for HTTPException handler
@app.get("/error")
async def error_example():
    raise HTTPException(status_code=400, detail="Custom error")

# Example echo route to test validation handler
@app.post("/echo", response_model=MessageResponse)
async def echo(item: MessageResponse):
    return item
