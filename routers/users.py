from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from dependencies import get_db, get_current_user, require_admin
from models.user import User
from schemas import (UserApproval, PendingUser, UserProfileUpdate,
                     UserPersonalInfo, UserPersonalInfoUpdate,
                     UserPreferences, UserPreferencesUpdate, PasswordUpdate)
from auth import verify_password, get_password_hash
from datetime import datetime

router = APIRouter(tags=["Users"])

@router.get("/admin/pending-users", response_model=List[PendingUser])
def get_pending_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return db.query(User).filter(User.is_approved == False).all()

@router.post("/admin/approve-user/{user_id}")
def approve_user(
    user_id: int,
    approval: UserApproval,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = approval.is_approved
    db.commit()
    return {"message": f"User {'approved' if approval.is_approved else 'rejected'} successfully"}

@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.put("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    user_update: UserProfileUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_update.nom: user.nom = user_update.nom
    if user_update.prenom: user.prenom = user_update.prenom
    if user_update.departement: user.departement = user_update.departement
    if user_update.role:
        if user_update.role not in ["prof", "employer"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = user_update.role
    db.commit()
    db.refresh(user)
    return {"message": "User updated successfully"}

@router.get("/public/users")
def get_all_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.get("/personal-info", response_model=UserPersonalInfo)
def get_personal_info(current_user: User = Depends(get_current_user)):
    return {"telephone": current_user.telephone}

@router.put("/personal-info")
def update_personal_info(
    info: UserPersonalInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if info.telephone:
        current_user.telephone = info.telephone
    db.commit()
    return {"message": "Personal information updated successfully"}

@router.get("/preferences", response_model=UserPreferences)
def get_preferences(current_user: User = Depends(get_current_user)):
    return {"language": current_user.language, "theme": current_user.theme}

@router.put("/preferences")
def update_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if preferences.language:
        if preferences.language not in ["fr", "en"]:
            raise HTTPException(status_code=400, detail="Invalid language")
        current_user.language = preferences.language
    if preferences.theme:
        if preferences.theme not in ["light", "dark"]:
            raise HTTPException(status_code=400, detail="Invalid theme")
        current_user.theme = preferences.theme
    db.commit()
    return {"message": "Preferences updated successfully"}

@router.put("/password")
def update_password(
    password_update: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if password_update.new_password != password_update.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    current_user.hashed_password = get_password_hash(password_update.new_password)
    db.commit()
    return {"message": "Password updated successfully"}