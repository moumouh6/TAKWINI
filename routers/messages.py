from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from dependencies import get_db, get_current_user
from models.user import User
from services.message_service import (
    create_message, get_user_messages, get_message,
    mark_message_as_read, delete_message
)

router = APIRouter(tags=["Messages"])

@router.post("/messages/")
def send_message(
    content: str = Form(...),
    receiver_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    return create_message(db, current_user.id, receiver_id, content, file)

@router.get("/messages/")
def get_messages(
    message_type: str = "received",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_user_messages(db, current_user.id, message_type, skip, limit)

@router.get("/messages/file/{message_id}")
def get_message_file(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    message = get_message(db, message_id, current_user.id)
    if not message or not message.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(message.file_path)

@router.get("/messages/{message_id}")
def read_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    message = get_message(db, message_id, current_user.id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@router.put("/messages/{message_id}/read")
def mark_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mark_message_as_read(db, message_id, current_user.id)
    return {"message": "Message marked as read"}

@router.delete("/messages/{message_id}")
def remove_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    delete_message(db, message_id, current_user.id)
    return {"message": "Message deleted"}