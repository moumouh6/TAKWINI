# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import SessionLocal
from config import settings
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_prof(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "prof":
        raise HTTPException(status_code=403, detail="Professor access required")
    return current_user

def require_prof_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("prof", "admin"):
        raise HTTPException(status_code=403, detail="Professor or admin access required")
    return current_user

def require_approved(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_approved:
        raise HTTPException(status_code=403, detail="Your account is not approved yet")
    return current_user