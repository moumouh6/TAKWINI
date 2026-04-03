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
from models.course import Course, CourseProgress
from sqlalchemy import func

router = APIRouter(tags=["Users"])

# ─── Users/Me ─────────────────────────────────────────────────
@router.get("/users/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Profile + course statistics for the logged-in user."""
    progress_records = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id
    ).all()

    total = len(progress_records)
    completed = len([p for p in progress_records if p.is_completed])
    avg_progress = (
        sum(p.progress for p in progress_records) / total
        if total > 0 else 0
    )

    # Average completion time in days
    completion_times = [
        (p.completion_date - p.start_date).days
        for p in progress_records
        if p.is_completed and p.completion_date
    ]
    avg_completion_days = (
        sum(completion_times) / len(completion_times)
        if completion_times else 0
    )

    courses_detail = []
    for p in progress_records:
        course = db.query(Course).filter(Course.id == p.course_id).first()
        if course:
            courses_detail.append({
                "nom_du_cours": course.title,
                "progres": f"{p.progress}%",
                "statut": p.status,
                "date_debut": p.start_date,
                "date_completion": p.completion_date,
            })

    return {
        "profile": {
            "nom": current_user.nom,
            "prenom": current_user.prenom,
            "email": current_user.email,
            "departement": current_user.departement,
            "fonction": current_user.role,
        },
        "statistics": {
            "total_cours_suivis": total,
            "cours_termines": completed,
            "progression_moyenne": f"{avg_progress:.1f}%",
            "temps_moyen_completion": f"{avg_completion_days:.1f} jours",
        },
        "courses": courses_detail
    }


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


# ─── Dashboard ────────────────────────────────────────────────
@router.get("/dashboard/admin")
def dashboard_admin(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    courses = db.query(Course).filter(
        Course.instructor_id == current_user.id
    ).all()
    return {"courses": courses}


@router.get("/dashboard/prof")
def dashboard_prof(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "prof":
        raise HTTPException(status_code=403, detail="Professor access required")
    courses = db.query(Course).filter(
        Course.instructor_id == current_user.id
    ).all()
    return {"courses": courses}


@router.get("/dashboard/employer")
def dashboard_employer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "employer":
        raise HTTPException(status_code=403, detail="Employer access required")
    # ← bug fixed: added department filter
    courses = db.query(Course).filter(
        Course.departement == current_user.departement
    ).all()
    return {"courses": courses}