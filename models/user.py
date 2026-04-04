from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True)
    prenom = Column(String, index=True)
    departement = Column(String)
    role = Column(String)
    email = Column(String, unique=True, index=True)
    telephone = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    language = Column(String, default="fr")  # Default language is French
    theme = Column(String, default="light")  # Default theme is light

    # Refresh token for "Remember Me" functionality
    refresh_token = Column(String, unique=True, nullable=True, index=True)
    refresh_token_expires = Column(DateTime, nullable=True)

    # Relationship with Course
    courses = relationship("Course", back_populates="instructor")
    course_progress = relationship("CourseProgress", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    conference_requests = relationship("ConferenceRequest", back_populates="requested_by") 

