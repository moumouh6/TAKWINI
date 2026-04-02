from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from models.user import Base
import enum

class ConferenceStatus(str, enum.Enum):
    pending = "En attente"
    approved = "Approuvé"
    denied = "Refusé"

class ConferenceRequest(Base):
    __tablename__ = "conference_requests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    link = Column(String, nullable=True)
    type = Column(String, nullable=False)  # e.g., "online" or "in-person"
    departement = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)  # Date de la conférence
    time = Column(String, nullable=False)  # Heure de la conférence (format HH:MM)

    requested_by_id = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(ConferenceStatus), default=ConferenceStatus.pending)
    created_at = Column(DateTime, default=datetime.now())
    
    # Add relationship with User
    requested_by = relationship("User", back_populates="conference_requests")
