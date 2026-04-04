# main.py
import logging
from fastapi import FastAPI, Request
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine
from models.user import Base
from auth import get_password_hash
from config import settings
from dependencies import get_db
from models.user import User
from sqlalchemy.exc import SQLAlchemyError
from routers import auth, users, courses, enrollment, notifications, messages, conferences

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

@app.middleware("http")
async def add_response_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000  # convert to ms
    response.headers["X-Response-Time"] = f"{duration:.2f}ms"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(enrollment.router)
app.include_router(notifications.router)
app.include_router(messages.router)
app.include_router(conferences.router)