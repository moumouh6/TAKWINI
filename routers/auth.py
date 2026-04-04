from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from dependencies import get_db
from models.user import User
import schemas
from schemas import Token, UserCreate, LogoutResponse, RefreshResponse
from auth import (
    verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_refresh_token, get_refresh_token_expiry, verify_refresh_token, revoke_refresh_token
)
from rate_limiter import limiter, LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

@router.post("/register", response_model=schemas.User)
@limiter.limit(REGISTER_RATE_LIMIT)
def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = User(
        nom=user.nom, prenom=user.prenom,
        departement=user.departement, role=user.role,
        email=user.email, telephone=user.telephone,
        hashed_password=get_password_hash(user.password),
        is_active=True, is_approved=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=Token)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login endpoint that returns access token and sets refresh token as httpOnly cookie.

    - Access token: Short-lived (30 min), sent in response body
    - Refresh token: Long-lived (7 days), stored in httpOnly cookie
    """
    user = get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Account not approved yet")

    # Create access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Create and store refresh token
    refresh_token = create_refresh_token()
    user.refresh_token = refresh_token
    user.refresh_token_expires = get_refresh_token_expiry()
    db.commit()

    # Set refresh token as httpOnly cookie
    # This cookie is automatically sent with subsequent requests
    # TODO: Set secure=True when deploying to production with HTTPS
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,           # JavaScript cannot access this
        secure=False,            # Set to True in production (HTTPS only)
        samesite="lax",          # CSRF protection
        max_age=7 * 24 * 60 * 60  # 7 days in seconds
    )

    logger.info(f"User logged in: {user.email}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("10/minute")  # Limit refresh attempts
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Refresh the access token using the refresh token from httpOnly cookie.

    - Returns new access token
    - Rotates the refresh token (issues new one for security)
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token provided",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Find user by refresh token
    user = db.query(User).filter(User.refresh_token == refresh_token).first()

    if not user or not verify_refresh_token(refresh_token, user):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create new access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Rotate refresh token (security best practice)
    new_refresh_token = create_refresh_token()
    user.refresh_token = new_refresh_token
    user.refresh_token_expires = get_refresh_token_expiry()
    db.commit()

    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=False,  # Set to True in production
        samesite="lax",
        max_age=7 * 24 * 60 * 60
    )

    logger.info(f"Token refreshed for user: {user.email}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Logout endpoint that revokes the refresh token.

    - Revokes refresh token in database
    - Clears httpOnly cookie
    - Access token remains valid until expiry (short-lived anyway)
    """
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Find and revoke the token
        user = db.query(User).filter(User.refresh_token == refresh_token).first()
        if user:
            revoke_refresh_token(user)
            db.commit()
            logger.info(f"User logged out: {user.email}")

    # Clear the cookie
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=False,  # Set to True in production
        samesite="lax"
    )

    return {"message": "Logged out successfully"}
