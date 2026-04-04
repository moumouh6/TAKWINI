from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import UploadFile


class UserBase(BaseModel):
    nom: str
    prenom: str
    departement: Optional[str] = None
    role: str
    email: EmailStr
    telephone: str

class UserCreate(UserBase):
    password: str
    confirm_password: str

class User(UserBase):
    id: int
    is_active: bool
    is_approved: bool

    model_config = ConfigDict(from_attributes=True)

class UserApproval(BaseModel):
    is_approved: bool

class PendingUser(User):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Course schemas
class CourseBase(BaseModel):
    title: str  # Nom du cours
    description: str  # Description
    departement: str  # Département
    external_links: Optional[str] = None  # Liens externes
    quiz_link: Optional[str] = None  # Lien du quiz

class CourseCreate(CourseBase):
    course_photo: Optional[UploadFile] = None  # Photo du cours
    course_material: Optional[UploadFile] = None  # Matériel de cours (PDF)
    course_record: Optional[UploadFile] = None  # Record du cours (optionnel)

class CourseMaterialBase(BaseModel):
    file_name: str
    file_type: str
    file_category: str  # 'photo', 'material', or 'record'
    image_url: Optional[str] = None  # URL Cloudinary si c'est une image

class CourseMaterialCreate(CourseMaterialBase):
    pass

class CourseMaterial(CourseMaterialBase):
    id: int
    course_id: int
    file_path: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Course(CourseBase):
    id: int
    instructor_id: int
    created_at: datetime
    updated_at: datetime
    materials: List[CourseMaterial] = []
    instructor: Optional[User] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationBase(BaseModel):
    title: str
    message: str
    type: str

class NotificationCreate(NotificationBase):
    pass

class Notification(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    related_course_id: Optional[int] = None
    related_material_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    notifications: List[Notification]
    unread_count: int

    model_config = ConfigDict(from_attributes=True)

class MessageBase(BaseModel):
    content: str
    receiver_id: int

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    sender_id: int
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserMessage(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    departement: str
    role: str

    model_config = ConfigDict(from_attributes=True)

class MessageInDB(Message):
    sender: UserMessage
    receiver: UserMessage

    model_config = ConfigDict(from_attributes=True)

class ConferenceStatus(str, Enum):
    pending = "En attente"
    approved = "Approuvé"
    denied = "Refusé"

class ConferenceRequestCreate(BaseModel):
    name: str
    description: Optional[str]
    link: Optional[str]
    type: str  # e.g., "online", "in-person"
    departement: str
    date: datetime
    time: str  # Format: "HH:MM"

class ConferenceRequestOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    link: Optional[str]
    type: str
    departement: str
    date: datetime
    time: str
    status: ConferenceStatus
    requested_by_id: int
    created_at: datetime
    requested_by: User

    model_config = ConfigDict(from_attributes=True)

class UserSettings(BaseModel):
    language: str  # "fr" or "en"
    theme: str     # "light" or "dark"

class UserSettingsUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    telephone: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None

class UserProfileUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    departement: Optional[str] = None
    role: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class UserSettingsResponse(BaseModel):
    nom: str
    prenom: str
    telephone: str
    language: str
    theme: str

    model_config = ConfigDict(from_attributes=True)

class UserPersonalInfo(BaseModel):
    telephone: str

    model_config = ConfigDict(from_attributes=True)

class UserPersonalInfoUpdate(BaseModel):
    telephone: Optional[str] = None

class UserPreferences(BaseModel):
    language: str
    theme: str

    model_config = ConfigDict(from_attributes=True)

class UserPreferencesUpdate(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None