# main.py
import logging
import time
import os
import shutil
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from database import engine
from models.user import Base
from auth import get_password_hash
from config import settings
from dependencies import get_db
from models.user import User
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from routers import auth, users, courses, enrollment, notifications, messages, conferences
from rate_limiter import limiter, rate_limit_exceeded_handler
from cache import _client as redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

def create_default_admin():
    try:
        db = next(get_db())
        admin = db.query(User).filter(
            User.email == settings.default_admin_email
        ).first()
        if not admin:
            db.add(User(
                nom="Admin", prenom="System", departement="RH",
                role="admin", email=settings.default_admin_email,
                telephone="0000000000",
                hashed_password=get_password_hash(settings.default_admin_password),
                is_active=True, is_approved=True
            ))
            db.commit()
            logger.info(f"✔ Admin created: {settings.default_admin_email}")
    except SQLAlchemyError as e:
        logger.error(f"Error creating admin: {e}")

create_default_admin()

app = FastAPI(
    title="TAKWINI",
    version="2.0",
    description="Plateforme de formation interne — Gulf Insurance Group Algeria",
    contact={
        "name": "GIG Algeria",
        "email": "admin@gig.dz"
    }
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

@app.middleware("http")
async def add_response_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000  # convert to ms
    response.headers["X-Response-Time"] = f"{duration:.2f}ms"
    return response

# Parse CORS origins from comma-separated string
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(enrollment.router)
app.include_router(notifications.router)
app.include_router(messages.router)
app.include_router(conferences.router)

# Health Check Endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns status of database, Redis, and disk space.
    """
    start_time = time.time()
    checks = {}
    overall_status = "healthy"

    # Check Database
    try:
        db_start = time.time()
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = f"connected ({int((time.time() - db_start) * 1000)}ms)"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        overall_status = "unhealthy"

    # Check Redis
    try:
        redis_start = time.time()
        if redis_client:
            redis_client.ping()
            checks["redis"] = f"connected ({int((time.time() - redis_start) * 1000)}ms)"
        else:
            checks["redis"] = "disabled"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        # Redis being down is not critical (has fallback)

    # Check Disk Space
    try:
        stat = shutil.disk_usage(settings.upload_dir if os.path.exists(settings.upload_dir) else ".")
        used_percent = (stat.used / stat.total) * 100
        checks["disk"] = f"{used_percent:.1f}% used"

        if used_percent > 90:
            checks["disk"] += " (WARNING: critical)"
            overall_status = "degraded"
        elif used_percent > 75:
            checks["disk"] += " (WARNING: high)"
    except Exception as e:
        checks["disk"] = f"error: {str(e)}"

    # Check Uploads Directory
    try:
        if os.path.exists(settings.upload_dir) and os.access(settings.upload_dir, os.W_OK):
            checks["uploads_dir"] = "ok"
        else:
            checks["uploads_dir"] = "not writable or missing"
            overall_status = "degraded"
    except Exception as e:
        checks["uploads_dir"] = f"error: {str(e)}"

    response_time = int((time.time() - start_time) * 1000)

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "response_time_ms": response_time,
        "checks": checks,
        "version": "2.0"
    }

# Root endpoint for quick check
@app.get("/")
async def root():
    return {
        "name": "TAKWINI API",
        "version": "2.0",
        "status": "running",
        "docs": "/docs"
    }