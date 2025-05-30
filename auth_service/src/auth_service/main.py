import logging
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth_service.routers import admin_client_routes
from auth_service.routers import admin_role_routes
from auth_service.routers import admin_permission_routes
from auth_service.routers import admin_role_permission_routes
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

app = FastAPI(root_path=settings.root_path)

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

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
