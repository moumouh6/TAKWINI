from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from dependencies import get_db
from models.user import User
import schemas                                    # ← add this
from schemas import Token, UserCreate
from auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from rate_limiter import limiter, LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT

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
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Account not approved yet")
    token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}