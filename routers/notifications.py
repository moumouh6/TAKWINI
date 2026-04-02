from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
from models.user import User
from services.notification_service import get_user_notifications, mark_notification_as_read

router = APIRouter(tags=["Notifications"])

@router.get("/notifications/")
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_notifications(db, current_user.id)

@router.put("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mark_notification_as_read(db, notification_id, current_user.id)
    return {"message": "Notification marked as read"}