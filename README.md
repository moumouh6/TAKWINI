# TAKWINI - Backend System Architecture & API Documentation

> [!NOTE]
> TAKWINI Backend is a comprehensive RESTful API developed for Gulf Insurance Group (GIG) Algeria. It manages an online learning platform, user access, messaging, and department-based training workflows.

## Table of Contents
1. [Introduction](#introduction)
2. [System Architecture Overview](#system-architecture-overview)
3. [Step-by-Step How Services Work](#step-by-step-how-services-work)
4. [Database Architecture & Communication](#database-architecture--communication)
5. [REST API Design & Endpoints](#rest-api-design--endpoints)
6. [Authentication System](#authentication-system)
7. [Notifications System](#notifications-system)
8. [Messaging System](#messaging-system)
9. [Caching Strategy](#caching-strategy)
10. [Technology Stack](#technology-stack)
11. [Setup & Deployment](#setup--deployment)
12. [Future Improvements](#future-improvements)

---

## Introduction

TAKWINI represents the backend logic for an enterprise learning platform with built-in corporate features:
- **Role-Based Workflows**: Handled for three primary roles — `admin`, `prof` (Professor), and `employer` (Employee).
- **Communication Flow**: Integrated messaging and internal notification systems.
- **Conferencing**: Built-in scheduling and approval flows for company conferences.
- **Resource Management**: Course materials (PDFs, Videos, Attachments) managed locally and via Cloudinary.

---

## System Architecture Overview

The platform follows a **Layered Service-Oriented Architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT (Frontend)                              │
│              HTML/CSS/JavaScript - Fetch API calls to /token            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTP/HTTPS Requests (JSON + Bearer Token)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION (main.py)                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      API Routes Layer                             │    │
│  │  - @app.post("/register")  - User registration                   │    │
│  │  - @app.post("/token")     - JWT token generation                │    │
│  │  - @app.get("/courses/")   - Course retrieval                    │    │
│  │  - @app.post("/messages/") - Message creation                    │    │
│  │  - @app.get("/notifications/") - Notification retrieval           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Authentication Middleware                       │    │
│  │  - OAuth2PasswordBearer extracts Bearer token                    │    │
│  │  - JWT decode using SECRET_KEY                                    │    │
│  │  - Role-based access control (admin/prof/employer)                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Pydantic Schemas (schemas.py)                   │    │
│  │  - Request validation (UserCreate, CourseCreate, etc.)          │    │
│  │  - Response serialization (UserSchema, CourseSchema, etc.)      │    │
│  │  - Prevents sensitive data leakage (excludes hashed_password)    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER (services/)                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              notification_service.py                              │    │
│  │  - create_notification()                                          │    │
│  │  - notify_new_course() - notifies admin, profs, employers        │    │
│  │  - notify_conference_request()                                    │    │
│  │  - get_user_notifications()                                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              message_service.py                                   │    │
│  │  - create_message() - with optional file attachments             │    │
│  │  - get_user_messages() - received or sent                         │    │
│  │  - mark_message_as_read()                                         │    │
│  │  - delete_message()                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MODEL LAYER (models/)                              │
│  - user.py       : User model with relationships                        │
│  - course.py     : Course, CourseMaterial, CourseProgress              │
│  - message.py    : Message model for internal messaging                 │
│  - notification.py: Notification model for alerts                      │
│  - conference.py : ConferenceRequest model                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATABASE (PostgreSQL)                               │
│  - Relational storage with foreign key constraints                     │
│  - Connection pooling (pool_size=5, max_overflow=10)                   │
│  - Indexed columns for fast lookups (email, id, etc.)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                                  │
│  - Cloudinary: Video and image CDN storage                             │
│  - Local Storage: PDF files in uploads/pdfs/                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step How Services Work

### 1. User Registration Flow

```
Client Request                    Server Processing
─────────────                     ─────────────────
POST /register
{
  "nom": "John",
  "prenom": "Doe",
  "email": "john@gig.dz",
  "password": "secret123",
  "departement": "RH",
  "role": "employer"
}
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ main.py: register() endpoint                              │
│ 1. Validate password match (password == confirm_password) │
│ 2. Check if email already exists in database              │
│ 3. Hash password using bcrypt (get_password_hash)         │
│ 4. Create User object with is_approved=False              │
│ 5. Commit to database                                     │
│ 6. Return UserSchema (without hashed_password)            │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Response: 200 OK
{
  "id": 5,
  "nom": "John",
  "email": "john@gig.dz",
  "is_approved": false,
  ...
}
```

### 2. Authentication Flow (Login)

```
Client Request                    Server Processing
─────────────                     ─────────────────
POST /token (OAuth2 form data)
username=john@gig.dz
password=secret123
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ main.py: login_for_access_token()                          │
│ 1. authenticate_user(db, email, password)                  │
│    - Find user by email                                    │
│    - verify_password(plain, hashed) using bcrypt          │
│ 2. Check if user.is_approved == True                      │
│ 3. Create JWT token with 30-min expiration               │
│    - Payload: {"sub": user.email, "exp": datetime}         │
│    - Algorithm: HS256                                      │
│    - Secret: SECRET_KEY from environment                   │
│ 4. Return Token response                                   │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Course Creation Flow (Professor)

```
Client Request                    Server Processing
─────────────                     ─────────────────
POST /courses/ (Multipart Form)
- title: "Python Basics"
- description: "Introduction to Python"
- departement: "IT"
- course_image: [file]
- course_pdf: [file]
- course_video: [file] (optional)
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ main.py: upload_course()                                   │
│ 1. Create Course object in database                        │
│ 2. Upload course_image to Cloudinary                      │
│    - cloudinary.uploader.upload(file, folder="courses/")  │
│    - Returns secure_url                                    │
│ 3. Save course_pdf locally in uploads/pdfs/               │
│    - os.makedirs("uploads/pdfs", exist_ok=True)           │
│    - shutil.copyfileobj(file, buffer)                     │
│ 4. If course_video provided:                               │
│    - Upload to Cloudinary (resource_type="video")         │
│ 5. Create CourseMaterial records for each file             │
│ 6. Commit all to database                                  │
│ 7. Call notification services:                              │
│    - notify_new_course(db, course) → Admin                 │
│    - notify_professor_new_course(db, course) → Profs      │
│    - notify_employer_new_course(db, course) → Employers    │
│ 8. Return CourseSchema response                            │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Response: 201 Created
{
  "id": 12,
  "title": "Python Basics",
  "instructor": {...},
  "materials": [...],
  ...
}
```

### 4. Message Sending Flow

```
Client Request                    Server Processing
─────────────                     ─────────────────
POST /messages/
Authorization: Bearer <token>
{
  "receiver_id": 3,
  "content": "Meeting at 3 PM",
  "file": [optional attachment]
}
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ services/message_service.py: create_message()              │
│ 1. Create Message object                                   │
│ 2. If file provided:                                       │
│    - save_message_file(file, message_id)                  │
│    - Creates uploads/messages/{message_id}/ directory      │
│    - Saves file with timestamp prefix                      │
│    - Updates message.file_path and file_type               │
│ 3. Commit to database                                      │
│ 4. Use joinedload() to eager-load sender/receiver          │
│ 5. Return Message with relationships                       │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Response: 201 Created
{
  "id": 45,
  "sender_id": 2,
  "receiver_id": 3,
  "content": "Meeting at 3 PM",
  "is_read": false,
  "created_at": "2024-01-15T14:30:00Z",
  ...
}
```

### 5. Notification Retrieval Flow

```
Client Request                    Server Processing
─────────────                     ─────────────────
GET /notifications/
Authorization: Bearer <token>
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ services/notification_service.py: get_user_notifications() │
│ 1. Query all notifications for user_id                     │
│    - Order by created_at DESC                              │
│ 2. Count unread notifications                               │
│    - Filter where is_read == False                         │
│ 3. Return dict with:                                       │
│    - notifications: List[Notification]                     │
│    - unread_count: int                                    │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Response: 200 OK
{
  "notifications": [
    {
      "id": 101,
      "title": "Nouveau cours disponible",
      "message": "Python Basics est disponible",
      "type": "new_course_available",
      "is_read": false,
      ...
    }
  ],
  "unread_count": 5
}
```

---

## Database Architecture & Communication

### Database Schema

```sql
-- Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    nom VARCHAR NOT NULL,
    prenom VARCHAR NOT NULL,
    departement VARCHAR,
    role VARCHAR NOT NULL,  -- 'admin', 'prof', 'employer'
    email VARCHAR UNIQUE NOT NULL,
    telephone VARCHAR,
    hashed_password VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_approved BOOLEAN DEFAULT FALSE,  -- Requires admin approval
    created_at TIMESTAMP DEFAULT NOW(),
    language VARCHAR DEFAULT 'fr',
    theme VARCHAR DEFAULT 'light'
);

-- Courses Table
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    description TEXT,
    instructor_id INTEGER REFERENCES users(id),
    departement VARCHAR,
    external_links TEXT,
    quiz_link VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Course Materials Table
CREATE TABLE course_materials (
    id SERIAL PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    file_name VARCHAR,
    file_path VARCHAR,  -- Cloudinary URL or local path
    file_type VARCHAR,
    file_category VARCHAR,  -- 'photo', 'material', 'record'
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Course Progress Table
CREATE TABLE course_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    course_id INTEGER REFERENCES courses(id),
    progress FLOAT DEFAULT 0,
    status VARCHAR DEFAULT 'En cours',
    start_date TIMESTAMP DEFAULT NOW(),
    completion_date TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT NOW(),
    is_completed BOOLEAN DEFAULT FALSE
);

-- Messages Table
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id),
    receiver_id INTEGER REFERENCES users(id),
    content TEXT,
    file_path VARCHAR,
    file_type VARCHAR,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notifications Table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR NOT NULL,
    message TEXT,
    type VARCHAR,  -- 'new_course', 'account_request', etc.
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    related_course_id INTEGER REFERENCES courses(id),
    related_material_id INTEGER REFERENCES course_materials(id)
);

-- Conference Requests Table
CREATE TABLE conference_requests (
    id SERIAL PRIMARY KEY,
    requested_by_id INTEGER REFERENCES users(id),
    name VARCHAR NOT NULL,
    description TEXT,
    link VARCHAR,
    type VARCHAR,
    departement VARCHAR,
    date TIMESTAMP NOT NULL,
    time VARCHAR,
    status VARCHAR DEFAULT 'En attente',  -- 'En attente', 'Approuvé', 'Refusé'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### SQLAlchemy ORM Communication

```python
# database.py - Database Connection Setup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "postgresql://..."

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,           # Maximum permanent connections
    max_overflow=10,        # Temporary connections when pool exhausted
    pool_timeout=30,        # Wait time for available connection
    pool_recycle=1800,      # Recycle connections after 30 minutes
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency injection in FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db  # Provides database session to route handlers
    finally:
        db.close()  # Ensures connection is returned to pool
```

### Model Relationships

```python
# models/user.py
class User(Base):
    __tablename__ = "users"
    
    courses = relationship("Course", back_populates="instructor")
    course_progress = relationship("CourseProgress", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id")

# models/course.py
class Course(Base):
    __tablename__ = "courses"
    
    instructor = relationship("User", back_populates="courses")
    materials = relationship("CourseMaterial", back_populates="course")
    progress_records = relationship("CourseProgress", back_populates="course")
```

### Query Optimization Techniques

```python
# 1. Eager Loading - Prevents N+1 queries
courses = db.query(Course).options(
    joinedload(Course.instructor),    # Single JOIN instead of N queries
    joinedload(Course.materials)
).all()

# 2. Pagination - Limits result set
courses = query.offset(skip).limit(limit).all()

# 3. Indexed Columns
email = Column(String, unique=True, index=True)  # Fast email lookups
id = Column(Integer, primary_key=True, index=True)
```

---

## REST API Design & Endpoints

### API Structure

| Domain | Method | Endpoint | Description | Auth Required |
|--------|--------|----------|-------------|---------------|
| **Auth** | POST | `/register` | Register new user | No |
| | POST | `/token` | Login and get JWT | No |
| **Users** | GET | `/users/me` | Get current user profile | Yes |
| | PUT | `/users/settings` | Update user settings | Yes |
| | PUT | `/users/profile` | Update user profile | Yes |
| **Admin** | GET | `/admin/pending-users` | List pending approvals | Admin Only |
| | POST | `/admin/approve-user/{id}` | Approve/reject user | Admin Only |
| | DELETE | `/admin/users/{id}` | Delete user | Admin Only |
| **Courses** | POST | `/courses/` | Create course (with files) | Prof/Admin |
| | GET | `/courses/` | List all courses | Yes |
| | GET | `/courses/by-department` | Courses for user's dept | Yes |
| | GET | `/courses/{id}` | Get course details | Yes |
| | PUT | `/courses/{id}/progress` | Update progress | Yes |
| | POST | `/courses/{id}/enroll` | Enroll in course | Employer |
| **Messages** | POST | `/messages/` | Send message | Yes |
| | GET | `/messages/` | Get messages (sent/received) | Yes |
| | PUT | `/messages/{id}/read` | Mark as read | Yes |
| | DELETE | `/messages/{id}` | Delete message | Yes |
| **Notifications** | GET | `/notifications/` | Get notifications | Yes |
| | PUT | `/notifications/{id}/read` | Mark as read | Yes |
| **Conferences** | POST | `/request` | Create conference request | Prof/Admin |
| | GET | `/calendar` | Get approved conferences | Yes |
| | PUT | `/admin/approve/{id}` | Approve/deny conference | Admin Only |

### Request/Response Examples

#### Registration
```bash
POST /register
Content-Type: application/json

{
  "nom": "Ahmed",
  "prenom": "Bensalem",
  "email": "ahmed@gig.dz",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!",
  "departement": "IT",
  "role": "employer",
  "telephone": "0555123456"
}
```

#### Login
```bash
POST /token
Content-Type: application/x-www-form-urlencoded

username=ahmed@gig.dz&password=SecurePass123!
```

#### Create Course (Multipart)
```bash
POST /courses/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: multipart/form-data

title=Introduction to Python
description=Learn Python fundamentals
departement=IT
course_image=@python-logo.png
course_pdf=@python-course.pdf
course_video=@intro-video.mp4
```

---

## Authentication System

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    JWT AUTHENTICATION FLOW                      │
└─────────────────────────────────────────────────────────────────┘

1. USER CREDENTIALS
   email: ahmed@gig.dz
   password: SecurePass123!

2. PASSWORD HASHING (bcrypt)
   Plain: "SecurePass123!"
   ↓
   get_password_hash(password)
   ↓
   Hashed: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.j7g5E1z5.uZ2i2"

3. JWT TOKEN CREATION
   Payload: {"sub": "ahmed@gig.dz", "exp": 2024-01-15T15:30:00Z}
   ↓
   jwt.encode(payload, SECRET_KEY, algorithm="HS256")
   ↓
   Token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

4. TOKEN VERIFICATION (on each request)
   Extract: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
   ↓
   jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
   ↓
   Payload: {"sub": "ahmed@gig.dz", "exp": ...}
   ↓
   get_user_by_email("ahmed@gig.dz")
   ↓
   Return User object to route handler
```

### Security Implementation

```python
# auth.py - Authentication Configuration
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import timedelta

SECRET_KEY = os.getenv("SECRET_KEY")  # Environment variable
ALGORITHM = "HS256"                     # HMAC with SHA-256
ACCESS_TOKEN_EXPIRE_MINUTES = 30       # Token expires in 30 minutes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Verify bcrypt hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hash password using bcrypt"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token with expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

### Token Extraction Middleware

```python
# OAuth2PasswordBearer extracts token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
):
    """Dependency that validates token and returns user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

def verify_professor_or_admin(current_user: User = Depends(get_current_user)):
    """Role-based authorization"""
    if current_user.role not in ["prof", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only professors and administrators can perform this action"
        )
    return current_user
```

### Best Practices Implemented

| Practice | Implementation |
|----------|---------------|
| **Password Hashing** | bcrypt with automatic upgrade |
| **Token Expiration** | 30-minute access tokens |
| **Secure Token Storage** | HTTP-only cookies recommended (frontend) |
| **Role-Based Access** | Dependency injection for authorization |
| **Approval Workflow** | New users require admin approval |
| **Credential Validation** | JWT signature verification |

---

## Notifications System

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION FLOW                            │
└─────────────────────────────────────────────────────────────────┘

EVENT TRIGGERED
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ services/notification_service.py                                │
│                                                                 │
│ create_notification()                                           │
│   - user_id: Target user                                        │
│   - title: Short summary                                       │
│   - message: Detailed message                                 │
│   - type: Notification category                                 │
│   - course_id: Related course (optional)                        │
│   - Save to notifications table                                │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ NOTIFICATION TYPES                                               │
│                                                                 │
│ Account Management:                                             │
│   - account_request    : New user registration                 │
│   - account_approval   : Admin approved/rejected account       │
│                                                                 │
│ Course Events:                                                  │
│   - new_course         : Admin - New course created             │
│   - course_created     : Course published                       │
│   - course_deleted     : Course removed                         │
│   - material_added     : New material in course                │
│   - course_approval    : Course access approved/rejected        │
│                                                                 │
│ Conference Events:                                             │
│   - conference_request : New conference request                │
│   - conference_status  : Conference approved/rejected           │
│                                                                 │
│ Progress Events:                                                │
│   - progress_updated   : Course progress changed                │
└─────────────────────────────────────────────────────────────────┘
```

### Notification Service Implementation

```python
# services/notification_service.py

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    type: str,
    course_id: int = None
) -> Notification:
    """Create a notification in the database"""
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

def notify_new_course(db: Session, course: Course):
    """Notify admin when a new course is created"""
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

def notify_employer_new_course(db: Session, course: Course):
    """Notify all employers in the department"""
    employers = db.query(User).filter(
        User.role == "employer",
        User.departement == course.departement
    ).all()
    
    for employer in employers:
        create_notification(
            db=db,
            user_id=employer.id,
            title="Nouveau cours disponible",
            message=f"Un nouveau cours '{course.title}' est disponible",
            type="new_course_available",
            course_id=course.id
        )

def get_user_notifications(db: Session, user_id: int) -> Dict:
    """Get all notifications with unread count"""
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
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications/` | Get all notifications for current user |
| PUT | `/notifications/{id}/read` | Mark notification as read |
| PUT | `/notifications/read-all` | Mark all notifications as read |

---

## Messaging System

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MESSAGE FLOW                                │
└─────────────────────────────────────────────────────────────────┘

SENDER                    SERVER                         RECEIVER
───────                   ──────                         ─────────
Compose message
+ optional file
        │
        │ POST /messages/
        │ {
        │   "receiver_id": 5,
        │   "content": "Meeting at 3 PM"
        │ }
        │
        ├───────────────────────────────────────►
        │
        │              create_message() service
        │              - Validate sender/receiver
        │              - Save message to DB
        │              - If file: save_message_file()
        │
        │              File Storage:
        │              uploads/messages/{msg_id}/
        │                  20240115_143000_document.pdf
        │
        ▼
Message saved
{
  "id": 45,
  "sender_id": 2,
  "receiver_id": 5,
  "content": "Meeting at 3 PM",
  "is_read": false,
  ...
}
        │
        │◄────────────────────────────────────────
        │
        │ GET /messages/?type=received
        │
        ▼
```

### Message Service Implementation

```python
# services/message_service.py

def create_message(
    db: Session,
    sender_id: int,
    receiver_id: int,
    content: str,
    file: UploadFile = None
) -> Message:
    """Create a new message with optional file attachment"""
    message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Handle file attachment
    if file:
        file_path, file_type = save_message_file(file, message.id)
        message.file_path = file_path
        message.file_type = file_type
        db.commit()
        db.refresh(message)
    
    # Eager load relationships for response
    return db.query(Message).options(
        joinedload(Message.sender),
        joinedload(Message.receiver)
    ).filter(Message.id == message.id).first()

def save_message_file(file: UploadFile, message_id: int) -> tuple:
    """Save uploaded file to organized directory structure"""
    messages_dir = "uploads/messages"
    message_dir = os.path.join(messages_dir, str(message_id))
    os.makedirs(message_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(message_dir, filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
    
    return file_path, file.content_type

def get_user_messages(
    db: Session,
    user_id: int,
    message_type: str = "received",
    skip: int = 0,
    limit: int = 100
) -> List[Message]:
    """Get messages with pagination"""
    query = db.query(Message).options(
        joinedload(Message.sender),
        joinedload(Message.receiver)
    )
    
    if message_type == "received":
        query = query.filter(Message.receiver_id == user_id)
    else:
        query = query.filter(Message.sender_id == user_id)
    
    return query.order_by(Message.created_at.desc())\
        .offset(skip).limit(limit).all()

def delete_message(db: Session, message_id: int, user_id: int) -> bool:
    """Delete message (sender or receiver can delete)"""
    message = db.query(Message).filter(
        Message.id == message_id,
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ).first()
    
    if message:
        # Delete associated file
        if message.file_path and os.path.exists(message.file_path):
            os.remove(message.file_path)
        db.delete(message)
        db.commit()
        return True
    return False
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/messages/` | Send a message |
| GET | `/messages/` | Get messages (add `?type=received` or `?type=sent`) |
| GET | `/messages/{id}` | Get single message |
| PUT | `/messages/{id}/read` | Mark as read |
| DELETE | `/messages/{id}` | Delete message |
| GET | `/users/list` | Get list of users for message composition |

---

## Caching Strategy

### Current State & Recommendations

> [!TIP]
> The current implementation does not include caching. Here are recommendations for implementing Redis-based caching.

### Recommended Caching Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CACHING LAYER                                │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client     │────►│   FastAPI    │────►│    Redis     │
│   Request    │     │   Router     │     │    Cache     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                          │
                    Cache Hit?│
                    ────────┬───────
                    No      │      Yes
                    ▼                ▼
              ┌──────────┐     ┌──────────┐
              │PostgreSQL│     │Return    │
              │Database  │     │Cached    │
              └────┬─────┘     │Data      │
                   │          └──────────┘
                   ▼
              ┌──────────┐
              │ Store    │──────► Invalidate on write
              │ in Redis │
              └──────────┘
```

### Implementation Example

```python
# cache.py - Redis Caching Service
import redis
import json
from functools import wraps
from typing import Optional

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache(key_prefix: str, expire: int = 300):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{str(args)}:{str(kwargs)}"
            
            # Try cache first
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            redis_client.setex(cache_key, expire, json.dumps(result))
            
            return result
        return wrapper
    return decorator

# Usage in routes
@router.get("/courses/")
@cache(key_prefix="courses", expire=60)  # Cache for 60 seconds
async def get_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).all()
    return courses

# Cache invalidation on write
def invalidate_cache(pattern: str):
    """Delete cache entries matching pattern"""
    for key in redis_client.scan_iter(pattern):
        redis_client.delete(key)
```

### Cache Strategy by Endpoint

| Endpoint | Cache Strategy | TTL | Reason |
|----------|---------------|-----|--------|
| `GET /courses/` | Cache all courses list | 60s | Rarely changes |
| `GET /courses/{id}` | Cache individual course | 5min | Rarely changes |
| `GET /notifications/` | No cache | - | Must be real-time |
| `GET /messages/` | No cache | - | Must be real-time |
| `GET /users/me` | Cache with user ID key | 5min | Updates infrequently |
| `GET /admin/pending-users` | No cache | - | Real-time admin need |

### Benefits of Caching

1. **Reduced Database Load**: Fewer queries to PostgreSQL
2. **Faster Response Times**: Sub-millisecond Redis lookups
3. **Scalability**: Handle more concurrent users
4. **Cost Reduction**: Fewer database connections

---

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| **Framework** | FastAPI | Latest | High-performance async web framework |
| **Server** | Uvicorn | Latest | ASGI server for FastAPI |
| **ORM** | SQLAlchemy | Latest | Database object-relational mapping |
| **Database** | PostgreSQL | Latest | Relational database |
| **Validation** | Pydantic | Latest | Data validation and settings |
| **Auth** | python-jose | Latest | JWT token handling |
| **Password** | passlib | Latest | Bcrypt password hashing |
| **File Storage** | Cloudinary | Latest | CDN for images/videos |
| **Environment** | python-dotenv | Latest | Environment variable management |

### Dependencies (requirements.txt)

```
fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
cloudinary>=1.34.0
python-dotenv>=1.0.0
```

---

## Setup & Deployment

### Prerequisites
- Python 3.9+
- PostgreSQL database
- Cloudinary account (for media)

### Installation Steps

```bash
# 1. Clone repository
git clone <repository-url>
cd Backend-main

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Initialize database
python init_db.py

# 6. Run server
uvicorn main:app --reload
```

### Environment Variables (.env)

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=your_host
POSTGRES_PORT=5432
POSTGRES_DB=takwini

# Security
SECRET_KEY=your-secret-key-min-32-characters

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Default Admin (optional)
DEFAULT_ADMIN_EMAIL=admin@gig.dz
DEFAULT_ADMIN_PASSWORD=secure_password
```

### API Documentation

Once running, access:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Future Improvements

### 1. Route Modularization
Currently all routes are in `main.py`. Recommended structure:

```
Backend-main/
├── main.py                 # App initialization
├── routers/
│   ├── __init__.py
│   ├── auth.py            # Login, register
│   ├── users.py           # User endpoints
│   ├── courses.py         # Course endpoints
│   ├── messages.py        # Messaging endpoints
│   ├── notifications.py   # Notification endpoints
│   └── admin.py           # Admin-only endpoints
├── services/
│   ├── notification_service.py
│   └── message_service.py
└── models/
    ├── user.py
    ├── course.py
    └── ...
```

### 2. Async Task Queue (Celery)
For heavy operations:
- Email notifications
- Bulk file uploads
- Course enrollment processing

### 3. WebSocket Support
For real-time features:
- Live notifications
- Instant messaging
- Progress updates

### 4. Rate Limiting
Protect against abuse:
- Login attempts
- API requests per user
- File upload limits

### 5. API Versioning
For backward compatibility:
- `/api/v1/courses/`
- `/api/v2/courses/`

---

*Proprietary - Gulf Insurance Group (GIG) Algeria*
