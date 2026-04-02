from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from dependencies import get_db, get_current_user
from models.user import User
from models.course import Course, CourseProgress
from services.notification_service import notify_course_progress, create_notification

router = APIRouter(tags=["Enrollment"])

# ─── Enroll ───────────────────────────────────────────────────
@router.post("/courses/{course_id}/enroll")
def enroll_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled")

    progress = CourseProgress(
        user_id=current_user.id,
        course_id=course_id,
        progress=0.0,
        status="En cours",
        start_date=datetime.utcnow(),
        last_accessed=datetime.utcnow(),
        is_completed=False
    )
    db.add(progress)
    db.commit()

    create_notification(
        db, current_user.id,
        title="Inscription au cours",
        message=f"Vous êtes inscrit à '{course.title}'.",
        type="course_enrollment",
        course_id=course_id
    )
    return {"message": "Enrolled successfully"}

# ─── Get Progress ─────────────────────────────────────────────
@router.get("/courses/{course_id}/progress")
def get_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")
    progress.last_accessed = datetime.utcnow()
    db.commit()
    return progress

# ─── Update Progress ──────────────────────────────────────────
@router.put("/courses/{course_id}/progress")
def update_progress(
    course_id: int,
    progress_value: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")

    progress.progress = min(100.0, max(0.0, progress_value))
    progress.last_accessed = datetime.utcnow()

    if progress.progress >= 100 and not progress.is_completed:
        progress.is_completed = True
        progress.status = "Terminé"
        progress.completion_date = datetime.utcnow()
        course = db.query(Course).filter(Course.id == course_id).first()
        create_notification(
            db, current_user.id,
            title="Cours terminé",
            message=f"Vous avez terminé '{course.title}'.",
            type="course_completion",
            course_id=course_id
        )

    db.commit()
    notify_course_progress(db, current_user.id, course_id, progress.progress)
    return {"message": "Progress updated", "progress": progress.progress}

# ─── Complete Course ──────────────────────────────────────────
@router.put("/courses/{course_id}/complete")
def complete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")

    progress.progress = 100.0
    progress.is_completed = True
    progress.status = "Terminé"
    progress.completion_date = datetime.utcnow()
    db.commit()

    course = db.query(Course).filter(Course.id == course_id).first()
    create_notification(
        db, current_user.id,
        title="Cours terminé",
        message=f"Vous avez terminé '{course.title}'.",
        type="course_completion",
        course_id=course_id
    )
    return {"message": "Course marked as complete"}