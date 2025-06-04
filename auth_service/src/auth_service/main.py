import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gotrue.errors import AuthApiError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.bootstrap import bootstrap_admin_and_rbac
from auth_service.config import settings
from auth_service.db import get_db
from auth_service.logging_config import LoggingMiddleware, logger, setup_logging
from auth_service.rate_limiting import limiter, setup_rate_limiting
from auth_service.routers import (
    admin_client_role_routes,
    admin_client_routes,
    admin_permission_routes,
    admin_role_permission_routes,
    admin_role_routes,
    admin_user_role_routes,
)
from auth_service.routers.token_routes import router as token_router
from auth_service.routers.user_auth_routes import user_auth_router
from auth_service.schemas import MessageResponse
from auth_service.supabase_client import close_supabase_client
from auth_service.supabase_client import (
    get_supabase_client as get_general_supabase_client,
)
from auth_service.supabase_client import init_supabase_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup sequence initiated.")

    # 1. Initialize app-wide resources (like the global Supabase client)
    await init_supabase_client()

    # 2. Run bootstrap process
    logger.info("Running bootstrap process...")
    db_session_for_bootstrap: AsyncSession | None = None
    try:
        # Get a DB session specifically for bootstrap
        async for session in get_db():
            db_session_for_bootstrap = session
            break

        if db_session_for_bootstrap:
            # bootstrap_admin_and_rbac should now use get_supabase_admin_client() internally
            # for operations requiring service_role_key.
            success = await bootstrap_admin_and_rbac(db_session_for_bootstrap)
            if success:
                logger.info("Bootstrap process completed successfully.")
            else:
                logger.warning(
                    "Bootstrap process completed with errors or was skipped."
                )
            # Decide on commit/rollback based on bootstrap success if it performs DB operations
            # For now, assuming bootstrap handles its own commits/rollbacks for its tasks
        else:
            logger.error(
                "Failed to get DB session for bootstrap process during startup."
            )
            # You might want to raise an error here to prevent app startup if bootstrap is critical
    except Exception as e:
        logger.error(f"Error during bootstrap process: {str(e)}", exc_info=True)
        if db_session_for_bootstrap:
            await db_session_for_bootstrap.rollback()  # Rollback if bootstrap fails mid-DB-op
    finally:
        if db_session_for_bootstrap:
            await db_session_for_bootstrap.close()
            logger.info("Bootstrap DB session closed.")

    logger.info("Application startup complete.")
    yield
    # --- Application Shutdown ---
    logger.info("Application shutdown sequence initiated.")
    await close_supabase_client()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Authentication Service API",
    description="Authentication and Authorization service for managing users, application clients, roles, and permissions.",
    version="1.0.0",
    root_path=settings.root_path,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "User Authentication",
            "description": "Operations for user authentication including login, registration, password management, and profile management.",
        },
        {
            "name": "Token Acquisition",
            "description": "Operations for obtaining authentication tokens for machine-to-machine (M2M) communication.",
        },
        {
            "name": "Admin - App Clients",
            "description": "Administrative operations for managing application clients.",
        },
        {
            "name": "Admin - Roles",
            "description": "Administrative operations for managing roles.",
        },
        {
            "name": "Admin - Permissions",
            "description": "Administrative operations for managing permissions.",
        },
        {
            "name": "Admin - Role Permissions",
            "description": "Administrative operations for assigning permissions to roles.",
        },
        {
            "name": "Admin - User Roles",
            "description": "Administrative operations for assigning roles to users.",
        },
        {
            "name": "Admin - Client Roles",
            "description": "Administrative operations for assigning roles to application clients.",
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
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
        limit_string = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        parts = limit_string.split(" per ")
        if len(parts) == 2 and "minute" in parts[1]:
            # Default retry window is 1 minute
            retry_seconds = 60
        elif len(parts) == 2 and "hour" in parts[1]:
            # For hourly rate limits
            retry_seconds = 3600
        elif len(parts) == 2 and "day" in parts[1]:
            # For daily rate limits
            retry_seconds = 86400
    except Exception as e:
        logger.error(f"Error parsing rate limit message: {e}")

    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests", "retry_after": retry_seconds},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"ValidationError: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    # This will use the globally initialized client from supabase_client.py
    supabase_general_client: AsyncSupabaseClient = Depends(get_general_supabase_client),
):
    """
    Health check endpoint that verifies the service and its dependencies are working.
    Returns application status, version, and component health information.
    """
    import datetime

    from auth_service.supabase_client import (
        get_supabase_admin_client,  # For admin client test
    )

    # Initialize response object
    response = {
        "status": "ok",
        "version": app.version,
        "environment": str(settings.environment),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "components": {"api": {"status": "ok"}},
    }

    # Check database connectivity
    try:
        # Simple query to verify database connection
        await db.execute(text("SELECT 1"))
        response["components"]["database"] = {"status": "ok"}
    except Exception as e:
        logger.error(f"Health check - Database error: {str(e)}")
        response["components"]["database"] = {
            "status": "error",
            "message": "Database connection failed",
        }
        response["status"] = "degraded"

    # Supabase General Client (Anon Key) Check
    if supabase_general_client:
        response["components"]["supabase_general_client"] = {
            "status": "ok",
            "message": "Client initialized",
        }
        try:
            await supabase_general_client.auth.get_user(
                "a-dummy-non-jwt-token-for-healthcheck"
            )
        except AuthApiError as ae:  # Expecting an error due to bad JWT
            if "invalid JWT" in str(ae.message).lower() or (
                hasattr(ae, "status") and ae.status == 401
            ):
                response["components"]["supabase_general_client"][
                    "message"
                ] = "Client initialized, API reachable (test call failed as expected)."
            else:  # Unexpected error
                logger.error(
                    f"Health check - Supabase general client error: {str(ae)}",
                    exc_info=True,
                )
                response["components"]["supabase_general_client"] = {
                    "status": "error",
                    "message": f"API error: {str(ae)}",
                }
                response["status"] = "degraded"
        except Exception as e:
            logger.error(
                f"Health check - Supabase general client unexpected error: {str(e)}",
                exc_info=True,
            )
            response["components"]["supabase_general_client"] = {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }
            response["status"] = "degraded"
    else:
        response["components"]["supabase_general_client"] = {
            "status": "error",
            "message": "Client not initialized",
        }
        response["status"] = "degraded"

    # Supabase Admin Client (Service Role Key) Check
    admin_client_available = False
    try:
        async with await get_supabase_admin_client() as admin_client:
            # Try a benign admin operation, like listing users with a limit of 0 or 1.
            # This tests if the service role key is valid and has basic admin list permission.
            await admin_client.auth.admin.list_users(page=1, per_page=1)
            response["components"]["supabase_admin_client"] = {
                "status": "ok",
                "message": "Client initialized and admin list users accessible",
            }
            admin_client_available = True
    except AuthApiError as e:
        logger.error(
            f"Health check - Supabase admin client AuthApiError: {str(e)} (Status: {getattr(e, 'status', 'N/A')})",
            exc_info=False,
        )  # exc_info=False for potentially sensitive key issues
        response["components"]["supabase_admin_client"] = {
            "status": "error",
            "message": f"Admin API error: {e.message}",
        }
        response["status"] = "degraded"
    except Exception as e:
        logger.error(
            f"Health check - Supabase admin client unexpected error: {str(e)}",
            exc_info=True,
        )
        response["components"]["supabase_admin_client"] = {
            "status": "error",
            "message": f"Admin client unexpected error: {str(e)}",
        }
        response["status"] = "degraded"
    if (
        not admin_client_available
        and "supabase_admin_client" not in response["components"]
    ):  # if creation itself failed
        response["components"]["supabase_admin_client"] = {
            "status": "error",
            "message": "Failed to initialize admin client",
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
