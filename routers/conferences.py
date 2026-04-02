from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from dependencies import get_db, get_current_user, require_admin, require_prof_or_admin
from models.user import User
from models.conference import ConferenceRequest
from schemas import ConferenceRequestCreate, ConferenceRequestOut, ConferenceStatus
from services.notification_service import notify_conference_request, notify_conference_status
from datetime import datetime

router = APIRouter(tags=["Conferences"])

@router.post("/request")
def request_conference(
    data: ConferenceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_prof_or_admin)
):
    # Admin gets auto-approved, prof goes to pending
    initial_status = (
        ConferenceStatus.approved
        if current_user.role == "admin"
        else ConferenceStatus.pending
    )
    conference = ConferenceRequest(
        name=data.name,
        description=data.description,
        link=data.link,
        type=data.type,
        departement=data.departement,
        date=data.date,
        time=data.time,
        requested_by_id=current_user.id,
        status=initial_status
    )
    db.add(conference)
    db.commit()
    db.refresh(conference)
    if current_user.role == "prof":
        notify_conference_request(db, conference, current_user)
    return conference

@router.get("/admin/pending-conferences")
def get_pending_conferences(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return db.query(ConferenceRequest).filter(
        ConferenceRequest.status == ConferenceStatus.pending
    ).options(joinedload(ConferenceRequest.requested_by)).all()

@router.put("/admin/approve/{conf_id}")
def approve_conference(
    conf_id: int,
    approve: bool,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    conference = db.query(ConferenceRequest).filter(
        ConferenceRequest.id == conf_id
    ).first()
    if not conference:
        raise HTTPException(status_code=404, detail="Conference not found")
    conference.status = (
        ConferenceStatus.approved if approve else ConferenceStatus.denied
    )
    db.commit()
    notify_conference_status(db, conference)
    return {"message": f"Conference {'approved' if approve else 'denied'}"}

@router.get("/prof/my-conferences")
def get_my_conferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ConferenceRequest).filter(
        ConferenceRequest.requested_by_id == current_user.id
    ).order_by(ConferenceRequest.date.desc()).all()

@router.get("/calendar")
def get_calendar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(ConferenceRequest).options(
        joinedload(ConferenceRequest.requested_by)
    ).filter(ConferenceRequest.status == ConferenceStatus.approved)

    if current_user.role == "employer":
        query = query.filter(
            ConferenceRequest.departement == current_user.departement
        )
    return query.order_by(ConferenceRequest.date).all()

@router.get("/conferences/{conference_id}")
def get_conference(
    conference_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conference = db.query(ConferenceRequest).options(
        joinedload(ConferenceRequest.requested_by)
    ).filter(ConferenceRequest.id == conference_id).first()
    if not conference:
        raise HTTPException(status_code=404, detail="Conference not found")
    if (current_user.role == "employer" and
            conference.departement != current_user.departement):
        raise HTTPException(status_code=403, detail="Access denied")
    return conference

@router.delete("/conferences/{conference_name}")
def delete_conference(
    conference_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conference = db.query(ConferenceRequest).filter(
        ConferenceRequest.name == conference_name,
        ConferenceRequest.requested_by_id == current_user.id
    ).first()
    if not conference:
        raise HTTPException(status_code=404, detail="Conference not found")
    db.delete(conference)
    db.commit()
    return {"message": "Conference deleted successfully"}