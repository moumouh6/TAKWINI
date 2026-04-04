from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import settings
import secrets
import logging

logger = logging.getLogger(__name__)

# Security
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# Refresh token settings
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Refresh Token Functions ──────────────────────────────────────

def create_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(32)

def get_refresh_token_expiry() -> datetime:
    """Get the expiry date for a new refresh token."""
    return datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

def verify_refresh_token(token: str, user) -> bool:
    """Verify if a refresh token is valid for a user."""
    if not user or not user.refresh_token or not user.refresh_token_expires:
        return False

    # Check token matches and hasn't expired
    return (
        user.refresh_token == token and
        user.refresh_token_expires > datetime.utcnow()
    )

def revoke_refresh_token(user):
    """Revoke a user's refresh token (logout)."""
    user.refresh_token = None
    user.refresh_token_expires = None
    logger.info(f"Refresh token revoked for user: {user.email}")