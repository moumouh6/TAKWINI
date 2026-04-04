from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
from models.user import User
from services.notification_service import get_user_notifications, mark_notification_as_read
from cache import cache_get, cache_set, cache_delete, TTL_NOTIFICATIONS

router = APIRouter(tags=["Notifications"])

@router.get("/notifications/")
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cache_key = f"notifications:user:{current_user.id}"

    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    result = get_user_notifications(db, current_user.id)

    # serialize before storing — notifications contain datetime objects
    from schemas import Notification as NotificationSchema
    serialized = {
        "notifications": [
            NotificationSchema.model_validate(n, from_attributes=True).model_dump(mode="json")
            for n in result["notifications"]
        ],
        "unread_count": result["unread_count"]
    }
    cache_set(cache_key, serialized, TTL_NOTIFICATIONS)
    return result


@router.put("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mark_notification_as_read(db, notification_id, current_user.id)
    # invalidate this user's cache so unread_count updates immediately
    cache_delete(f"notifications:user:{current_user.id}")
    return {"message": "Notification marked as read"}