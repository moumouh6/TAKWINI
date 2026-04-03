from sqlalchemy.orm import Session
from models.notification import Notification
from models.user import User
from models.course import Course
from typing import Dict
from datetime import datetime


# ─── Core Functions ───────────────────────────────────────────

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    type: str,
    course_id: int = None
) -> Notification:
    """Create a single notification — use for one user only."""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        related_course_id=course_id,
        is_read=False,
        created_at=datetime.utcnow()
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def _bulk_notify(
    db: Session,
    user_ids: list,
    title: str,
    message: str,
    type: str,
    course_id: int = None
):
    """
    Create notifications for multiple users in ONE commit.
    This replaces the old loop that did one commit per user.
    """
    if not user_ids:
        return
    notifications = [
        Notification(
            user_id=uid,
            title=title,
            message=message,
            type=type,
            related_course_id=course_id,
            is_read=False,
            created_at=datetime.utcnow()
        )
        for uid in user_ids
    ]
    db.bulk_save_objects(notifications)
    db.commit()


# ─── Read Functions ───────────────────────────────────────────

def get_user_notifications(db: Session, user_id: int) -> Dict:
    """Get all notifications for a user with unread count."""
    notifications = db.query(Notification)\
        .filter(Notification.user_id == user_id)\
        .order_by(Notification.created_at.desc())\
        .all()

    unread_count = db.query(Notification)\
        .filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    return {"notifications": notifications, "unread_count": unread_count}


def mark_notification_as_read(
    db: Session, notification_id: int, user_id: int
) -> Notification:
    """Mark a specific notification as read."""
    try:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if notification:
            notification.is_read = True
            db.commit()
            db.refresh(notification)
        return notification
    except Exception as e:
        db.rollback()
        raise e


# ─── Course Notifications ─────────────────────────────────────

def notify_new_course(db: Session, course: Course):
    """Notify admin about new course — single user, single commit."""
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        create_notification(
            db=db,
            user_id=admin.id,
            title="Nouveau cours ajouté",
            message=f"Le cours '{course.title}' a été ajouté",
            type="new_course",
            course_id=course.id
        )


def notify_professor_new_course(db: Session, course: Course):
    """
    Notify all professors in the department — ONE commit for all.
    Old code: 10 professors = 10 commits
    New code: 10 professors = 1 commit
    """
    prof_ids = [
        u.id for u in db.query(User).filter(
            User.role == "prof",
            User.departement == course.departement
        ).all()
    ]
    _bulk_notify(
        db, prof_ids,
        title="Nouveau cours dans votre département",
        message=f"Le cours '{course.title}' a été ajouté dans votre département",
        type="department_new_course",
        course_id=course.id
    )


def notify_employer_new_course(db: Session, course: Course):
    """
    Notify all employers in the department — ONE commit for all.
    Old code: 50 employers = 50 commits
    New code: 50 employers = 1 commit
    """
    employer_ids = [
        u.id for u in db.query(User).filter(
            User.role == "employer",
            User.departement == course.departement
        ).all()
    ]
    _bulk_notify(
        db, employer_ids,
        title="Nouveau cours disponible",
        message=f"Le cours '{course.title}' est disponible dans votre département",
        type="new_course_available",
        course_id=course.id
    )


def notify_course_deleted(db: Session, course: Course):
    """Notify admin when a course is deleted."""
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        create_notification(
            db=db,
            user_id=admin.id,
            title="Cours supprimé",
            message=f"Le cours '{course.title}' a été supprimé",
            type="course_deleted",
            course_id=course.id
        )


def notify_material_added(db: Session, course: Course, material):
    """
    Notify admin + all enrolled students — ONE commit for students.
    Old code: 30 students = 31 commits (1 admin + 30 students)
    New code: 30 students = 2 commits (1 admin + 1 bulk)
    """
    # Notify admin — single commit
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        create_notification(
            db=db,
            user_id=admin.id,
            title="Nouveau matériel ajouté",
            message=f"Un nouveau matériel a été ajouté au cours '{course.title}'",
            type="material_added",
            course_id=course.id
        )

    # Notify all enrolled students — one bulk commit
    student_ids = [p.user_id for p in course.progress_records]
    _bulk_notify(
        db, student_ids,
        title="Nouveau matériel disponible",
        message=f"Un nouveau matériel est disponible dans '{course.title}'",
        type="material_added",
        course_id=course.id
    )


def notify_course_progress(
    db: Session, user_id: int, course_id: int, progress: float
):
    """Notify user about their progress update."""
    # ← fixed: takes course_id (int) not course object
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        create_notification(
            db=db,
            user_id=user_id,
            title="Progression mise à jour",
            message=f"Votre progression est maintenant de {progress}%",
            type="progress_updated",
            course_id=course_id
        )


# ─── Conference Notifications ─────────────────────────────────

def notify_conference_request(db: Session, conference, user: User):
    """
    Notify admin about a new conference request.
    Fixed signature — takes conference object + user object.
    """
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        create_notification(
            db=db,
            user_id=admin.id,
            title="Nouvelle demande de conférence",
            message=f"{user.nom} {user.prenom} a demandé la conférence '{conference.name}'",
            type="conference_request"
        )


def notify_conference_status(db: Session, conference):
    """
    Notify professor about conference approval/denial.
    Fixed signature — takes conference object only.
    """
    is_approved = conference.status.value == "Approuvé"
    status = "approuvée" if is_approved else "refusée"
    create_notification(
        db=db,
        user_id=conference.requested_by_id,
        title="Statut de votre conférence",
        message=f"Votre demande pour '{conference.name}' a été {status}",
        type="conference_status"
    )


# ─── Account Notifications ────────────────────────────────────

def notify_new_account_request(db: Session, user: User):
    """Notify admin about new account registration."""
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        create_notification(
            db=db,
            user_id=admin.id,
            title="Nouvelle demande de compte",
            message=f"{user.nom} {user.prenom} a demandé un compte",
            type="account_request"
        )


def notify_account_approval(db: Session, user: User, is_approved: bool):
    """Notify user about account approval/rejection."""
    status = "approuvé" if is_approved else "refusé"
    create_notification(
        db=db,
        user_id=user.id,
        title="Statut de votre compte",
        message=f"Votre compte a été {status}",
        type="account_approval"
    )