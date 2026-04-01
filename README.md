# TAKWINI - Backend API Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Technologies](#technologies)
3. [Project Structure](#project-structure)
4. [Database Schema](#database-schema)
5. [Authentication & Authorization](#authentication--authorization)
6. [API Endpoints](#api-endpoints)
   - [Authentication](#authentication-1)
   - [User Management](#user-management)
   - [Course Management](#course-management)
   - [Notifications](#notifications)
   - [Messaging](#messaging)
   - [Conferences](#conferences)
   - [Dashboards](#dashboards)
   - [User Settings](#user-settings)
7. [Request/Response Schemas](#requestresponse-schemas)
8. [Services](#services)
9. [Utilities](#utilities)
10. [Configuration](#configuration)
11. [Deployment](#deployment)

---

## Introduction

TAKWINI Backend is a RESTful API developed for Gulf Insurance Group (GIG) Algeria, designed to manage an online learning platform. This API provides comprehensive functionality for user management, course delivery, internal communications, employee progress tracking, and conference scheduling.

The platform supports three user roles:
- **Admin**: Full system access, user approval, course management oversight
- **Professor**: Course creation, employee progress monitoring, conference requests
- **Employer/Employee**: Course enrollment, progress tracking, communication

---

## Technologies

| Category | Technology |
|----------|------------|
| Framework | FastAPI 0.104.1 |
| Database | PostgreSQL (Railway hosted) |
| ORM | SQLAlchemy 2.0.23 |
| Authentication | JWT (JSON Web Tokens) |
| Password Hashing | bcrypt via passlib |
| Data Validation | Pydantic 2.5.2 |
| File Storage | Local filesystem + Cloudinary |
| Server | Uvicorn 0.24.0 |
| Environment | python-dotenv 1.0.0 |

---

## Project Structure

```
Backend-main/
├── models/                      # SQLAlchemy database models
│   ├── __init__.py             # Model exports
│   ├── base.py                 # Declarative base configuration
│   ├── user.py                 # User model
│   ├── course.py               # Course, CourseMaterial, CourseProgress models
│   ├── notification.py          # Notification model
│   ├── message.py              # Message model
│   └── conference.py           # ConferenceRequest model
├── schemas/                    # Pydantic schemas for request/response validation
├── services/                   # Business logic services
│   ├── notification_service.py # Notification handling
│   └── message_service.py      # Messaging functionality
├── static/                     # Static files
│   └── uploads/               # Uploaded files (courses, attachments)
├── main.py                    # Main FastAPI application with all routes
├── database.py               # Database configuration and session management
├── auth.py                   # Authentication utilities (JWT, password hashing)
├── schemas.py                # Pydantic request/response models
├── utils.py                  # Utility functions (file handling)
├── requirements.txt          # Python dependencies
└── README.md                 # Documentation
```

---

## Database Schema

### Users Table (`users`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique user identifier |
| nom | VARCHAR | | User's last name |
| prenom | VARCHAR | | User's first name |
| departement | VARCHAR | | Department name |
| role | VARCHAR | | User role: 'admin', 'prof', 'employer' |
| email | VARCHAR | UNIQUE, INDEX | User email address |
| telephone | VARCHAR | | Phone number |
| hashed_password | VARCHAR | | bcrypt hashed password |
| is_active | BOOLEAN | DEFAULT TRUE | Account active status |
| is_approved | BOOLEAN | DEFAULT FALSE | Admin approval status |
| created_at | DATETIME | DEFAULT NOW | Account creation timestamp |
| language | VARCHAR | DEFAULT 'fr' | Preferred language |
| theme | VARCHAR | DEFAULT 'light' | UI theme preference |

**Relationships:**
- One-to-Many with `courses` (as instructor)
- One-to-Many with `course_progress`
- One-to-Many with `notifications`
- One-to-Many with `sent_messages`
- One-to-Many with `received_messages`
- One-to-Many with `conference_requests`

### Courses Table (`courses`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique course identifier |
| title | VARCHAR | INDEX | Course title |
| description | TEXT | | Course description |
| instructor_id | INTEGER | FOREIGN KEY (users.id) | Course instructor |
| departement | VARCHAR | | Department for access control |
| external_links | TEXT | NULLABLE | Additional resource links |
| quiz_link | VARCHAR | NULLABLE | External quiz URL |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| updated_at | DATETIME | DEFAULT NOW | Last update timestamp |

**Relationships:**
- Many-to-One with `users` (instructor)
- One-to-Many with `course_materials`
- One-to-Many with `course_progress`
- One-to-Many with `notifications`

### Course Materials Table (`course_materials`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique material identifier |
| course_id | INTEGER | FOREIGN KEY (courses.id) | Parent course |
| file_name | VARCHAR | | Original filename |
| file_path | VARCHAR | | Storage path (local or Cloudinary URL) |
| file_type | VARCHAR | | MIME type |
| file_category | VARCHAR | | 'photo', 'material', or 'record' |
| uploaded_at | DATETIME | DEFAULT NOW | Upload timestamp |

**File Categories:**
- `photo`: Course thumbnail image (stored on Cloudinary)
- `material`: PDF documents (stored locally)
- `record`: Video recordings (stored on Cloudinary)

### Course Progress Table (`course_progress`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique progress record ID |
| user_id | INTEGER | FOREIGN KEY (users.id) | Student |
| course_id | INTEGER | FOREIGN KEY (courses.id) | Course |
| progress | FLOAT | DEFAULT 0 | Completion percentage (0-100) |
| status | VARCHAR | DEFAULT 'En cours' | Status: 'En cours', 'Terminé' |
| start_date | DATETIME | DEFAULT NOW | Enrollment date |
| completion_date | DATETIME | NULLABLE | Completion timestamp |
| last_accessed | DATETIME | DEFAULT NOW | Last access timestamp |
| is_completed | BOOLEAN | DEFAULT FALSE | Completion flag |

### Notifications Table (`notifications`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique notification ID |
| user_id | INTEGER | FOREIGN KEY (users.id) | Recipient |
| title | VARCHAR | | Notification title |
| message | TEXT | | Notification content |
| type | VARCHAR | | Type: 'course_created', 'course_deleted', etc. |
| is_read | BOOLEAN | DEFAULT FALSE | Read status |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| related_course_id | INTEGER | FOREIGN KEY (courses.id), NULLABLE | Related course |
| related_material_id | INTEGER | FOREIGN KEY (course_materials.id), NULLABLE | Related material |

**Notification Types:**
- `account_request`: New user registration
- `account_approval`: Account approved/rejected
- `course_request`: Course access request
- `course_approval`: Course access approved/rejected
- `new_course`: New course created
- `new_course_available`: Course available for enrollment
- `department_new_course`: New course in department
- `course_created`: Course created notification
- `course_deleted`: Course deleted notification
- `course_completion`: Course marked as completed
- `material_added`: New course material available
- `progress_updated`: Progress updated notification
- `conference_request`: Conference request submitted
- `conference_status`: Conference approved/denied

### Messages Table (`messages`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique message ID |
| sender_id | INTEGER | FOREIGN KEY (users.id) | Sender |
| receiver_id | INTEGER | FOREIGN KEY (users.id) | Recipient |
| content | TEXT | | Message content |
| file_path | VARCHAR | NULLABLE | Attachment path |
| file_type | VARCHAR | NULLABLE | Attachment MIME type |
| is_read | BOOLEAN | DEFAULT FALSE | Read status |
| created_at | DATETIME | DEFAULT NOW | Send timestamp |

### Conference Requests Table (`conference_requests`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Unique request ID |
| name | VARCHAR | | Conference title |
| description | TEXT | NULLABLE | Conference description |
| link | VARCHAR | NULLABLE | Meeting link |
| type | VARCHAR | | Type: 'online', 'in-person' |
| departement | VARCHAR | | Target department |
| date | DATETIME | | Conference date |
| time | VARCHAR | | Conference time (HH:MM format) |
| requested_by_id | INTEGER | FOREIGN KEY (users.id) | Requester |
| status | ENUM | DEFAULT 'En attente' | Status: 'En attente', 'Approuvé', 'Refusé' |
| created_at | DATETIME | DEFAULT NOW | Request timestamp |

---

## Authentication & Authorization

### JWT Authentication

The API uses JWT (JSON Web Token) for authentication:

- **Algorithm**: HS256
- **Token Expiration**: 30 minutes
- **Token Location**: Authorization header (`Bearer <token>`)

### Password Security

- **Hashing Algorithm**: bcrypt
- **Context**: CryptContext with automatic depreciation handling

### Role-Based Access Control

| Role | Permissions |
|------|-------------|
| admin | Full access to all endpoints, user management, approvals |
| prof | Create/manage own courses, view enrolled students, request conferences |
| employer | View department courses, enroll, track progress, messaging |

### Default Admin Account

On first startup, a default admin is created:
- **Email**: admin@gig.dz (configurable via `DEFAULT_ADMIN_EMAIL`)
- **Password**: admin123 (configurable via `DEFAULT_ADMIN_PASSWORD`)

---

## API Endpoints

### Authentication

#### POST /register
Register a new user account.

**Request Body:**
```json
{
  "nom": "string",
  "prenom": "string",
  "departement": "string",
  "role": "prof|employer",
  "email": "user@example.com",
  "telephone": "string",
  "password": "string",
  "confirm_password": "string"
}
```

**Response:** `User` schema (201 Created)

**Notes:**
- New users are created with `is_approved: false`
- Requires admin approval before login

---

#### POST /token
Authenticate and receive access token.

**Request:** OAuth2PasswordRequestForm
- `username`: Email address
- `password`: Password

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Notes:**
- Returns 403 if account not approved
- Token expires after 30 minutes

---

### User Management

#### GET /users/me
Get current user profile with statistics.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "profile": {
    "nom": "string",
    "prenom": "string",
    "email": "string",
    "telephone": "string",
    "departement": "string",
    "fonction": "string"
  },
  "statistics": {
    "total_cours_suivis": 0,
    "cours_termines": 0,
    "progression_moyenne": "0.0%",
    "temps_moyen_completion": "0.0 jours"
  },
  "courses": [...]
}
```

---

#### GET /admin/pending-users
Get list of users awaiting approval.

**Authorization:** Admin only

**Response:** `List[PendingUser]`

---

#### POST /admin/approve-user/{user_id}
Approve or reject a user registration.

**Authorization:** Admin only

**Request Body:**
```json
{
  "is_approved": true
}
```

**Response:** `User` schema

---

#### DELETE /admin/users/{user_id}
Delete a user account.

**Authorization:** Admin only

**Notes:** Admin cannot delete their own account

---

#### PUT /admin/users/{user_id}
Update user information.

**Authorization:** Admin only

**Request Body:**
```json
{
  "nom": "string",
  "prenom": "string",
  "departement": "string",
  "role": "prof|employer"
}
```

---

### Course Management

#### POST /courses/
Create a new course with materials.

**Authorization:** Professor or Admin

**Form Data:**
- `title`: Course title (required)
- `description`: Course description (required)
- `departement`: Department name (required)
- `course_image`: Course thumbnail (required, image file)
- `course_pdf`: Course material PDF (required)
- `external_links`: Additional links (optional)
- `quiz_link`: Quiz URL (optional)
- `course_video`: Video recording (optional)

**Response:** `Course` schema with materials

**Notes:**
- Course image uploaded to Cloudinary
- PDF stored locally in `uploads/pdfs/`
- Video uploaded to Cloudinary
- Notifications sent to relevant users

---

#### GET /courses/
List all courses.

**Authorization:** All authenticated users

**Query Parameters:**
- `skip`: Pagination offset (default: 0)
- `limit`: Page size (default: 100)

**Notes:**
- Employers only see courses from their department
- Professors/Admins see all courses

---

#### GET /courses/by-department
Get courses for current user's department.

**Authorization:** All authenticated users

**Response:** `List[Course]` schema

---

#### GET /courses/{course_id}
Get course details.

**Authorization:** All authenticated users

**Response:** `Course` schema with materials

---

#### GET /courses/{course_id}/materials/
Get course materials list.

**Authorization:** All authenticated users

**Response:** `List[CourseMaterial]` schema

---

#### PUT /courses/{course_id}
Update course information.

**Authorization:** Course instructor or Admin

**Request Body:** `CourseBase` schema

---

#### DELETE /courses/{course_id}
Delete a course.

**Authorization:** Course instructor or Admin

**Notes:**
- Sends deletion notification to admin
- Cascades to delete associated materials

---

#### DELETE /courses/{course_id}/materials/{material_id}
Delete specific course material.

**Authorization:** Course instructor or Admin

---

### Course Enrollment & Progress

#### POST /courses/{course_id}/enroll
Enroll in a course.

**Authorization:** All authenticated users

**Response:**
```json
{
  "success": true,
  "message": "string",
  "course": {
    "id": 0,
    "title": "string",
    "instructor": "string",
    "departement": "string",
    "start_date": "datetime",
    "status": "En cours",
    "progress": "0.0%"
  }
}
```

**Notes:**
- Creates initial progress record
- Sends enrollment notification

---

#### PUT /courses/{course_id}/complete
Mark course as completed.

**Authorization:** Enrolled users

**Response:**
```json
{
  "success": true,
  "message": "string",
  "course": {...},
  "completion_details": {
    "completion_date": "dd/mm/yyyy",
    "total_duration": "x jours",
    "progress": "100%",
    "status": "Terminé"
  }
}
```

---

#### GET /courses/{course_id}/progress
Get user's progress in a course.

**Authorization:** Enrolled users

**Response:**
```json
{
  "success": true,
  "course_id": 0,
  "course_title": "string",
  "instructor": {...},
  "progress_details": {
    "enrollment_date": "dd/mm/yyyy",
    "last_accessed": "dd/mm/yyyy HH:MM",
    "completion_date": "dd/mm/yyyy|null",
    "progress_value": 0.0,
    "progress_percent": "0.0%",
    "status": "string",
    "is_completed": false,
    "duration": "x jours"
  }
}
```

---

#### PUT /courses/{course_id}/progress
Update course progress.

**Authorization:** Enrolled users

**Query Parameters:**
- `progress_value`: Float (0-100)

**Notes:**
- Auto-completes course when progress reaches 100%

---

### Notifications

#### GET /notifications/
Get user's notifications.

**Authorization:** All authenticated users

**Response:**
```json
{
  "notifications": [
    {
      "id": 0,
      "user_id": 0,
      "title": "string",
      "message": "string",
      "type": "string",
      "is_read": false,
      "created_at": "datetime",
      "related_course_id": 0,
      "related_material_id": 0
    }
  ],
  "unread_count": 0
}
```

**Notes:**
- Notifications marked as read when fetched

---

#### PUT /notifications/{notification_id}/read
Mark notification as read.

**Authorization:** Notification owner

**Response:**
```json
{
  "message": "Notification marked as read",
  "notification": {...}
}
```

---

### Messaging

#### POST /messages/
Send a message.

**Authorization:** All authenticated users

**Form Data:**
- `content`: Message text (required)
- `receiver_id`: Recipient user ID (required)
- `file`: Attachment file (optional)

**Response:** `MessageInDB` schema

---

#### GET /messages/
Get user's messages.

**Authorization:** All authenticated users

**Query Parameters:**
- `message_type`: "received" or "sent" (default: "received")
- `skip`: Pagination offset (default: 0)
- `limit`: Page size (default: 100)

**Response:** `List[MessageInDB]`

---

#### GET /messages/{message_id}
Get specific message details.

**Authorization:** Message sender or receiver

**Response:** `MessageInDB` schema

**Notes:**
- Auto-marks as read when viewed by receiver

---

#### PUT /messages/{message_id}/read
Mark message as read.

**Authorization:** Message receiver

---

#### DELETE /messages/{message_id}
Delete a message.

**Authorization:** Message sender or receiver

---

#### GET /messages/file/{message_id}
Download message attachment.

**Authorization:** Message sender or receiver

**Response:** File download

---

### Conferences

#### POST /request
Create a conference request.

**Authorization:** Professor or Admin

**Form Data:**
- `name`: Conference title (required)
- `description`: Conference description (optional)
- `link`: Meeting link (optional)
- `type`: "online" or "in-person" (required)
- `departement`: Target department (required)
- `date`: Date in YYYY-MM-DD format (required)
- `time`: Time in HH:MM format (required)

**Response:** `ConferenceRequestOut` schema

**Notes:**
- Professors create with "En attente" status
- Admins create with "Approuvé" status
- Sends notification to admin

---

#### PUT /admin/approve/{conf_id}
Approve or deny conference request.

**Authorization:** Admin only

**Query Parameters:**
- `approve`: Boolean

**Response:** `ConferenceRequestOut` schema

**Notes:**
- Sends status notification to requester

---

#### GET /admin/pending-conferences
Get pending conference requests.

**Authorization:** Admin only

**Response:** `List[ConferenceRequestOut]`

---

#### GET /prof/my-conferences
Get professor's conference requests.

**Authorization:** Professor only

**Response:** `List[ConferenceRequestOut]`

---

#### GET /calendar
Get approved conferences calendar.

**Authorization:** All authenticated users

**Notes:**
- Employers see only their department's conferences
- Professors/Admins see all conferences

**Response:** `List[ConferenceRequestOut]`

---

#### GET /conferences/{conference_id}
Get conference details.

**Authorization:** All authenticated users

**Notes:**
- Employers can only view their department's conferences

---

#### DELETE /conferences/{conference_name}
Delete a conference request.

**Authorization:** Request creator only

---

### Dashboards

#### GET /dashboard/admin
Get admin dashboard data.

**Authorization:** Admin only

**Response:** List of admin's courses

---

#### GET /dashboard/prof
Get professor dashboard data.

**Authorization:** Professor only

**Response:** List of professor's courses with materials

---

#### GET /dashboard/employer
Get employer dashboard data.

**Authorization:** Employer only

**Response:**
```json
{
  "available_courses": [
    {
      "id": 0,
      "title": "string",
      "description": "string",
      "instructor": {"nom": "string"},
      "materials_count": 0
    }
  ]
}
```

---

### User Settings

#### GET /personal-info
Get user's personal information.

**Authorization:** All authenticated users

**Response:**
```json
{
  "telephone": "string"
}
```

---

#### PUT /personal-info
Update personal information.

**Authorization:** All authenticated users

**Request Body:**
```json
{
  "telephone": "string"
}
```

---

#### GET /preferences
Get user preferences.

**Authorization:** All authenticated users

**Response:**
```json
{
  "language": "fr|en",
  "theme": "light|dark"
}
```

---

#### PUT /preferences
Update user preferences.

**Authorization:** All authenticated users

**Request Body:**
```json
{
  "language": "fr|en",
  "theme": "light|dark"
}
```

---

#### PUT /password
Update user password.

**Authorization:** All authenticated users

**Request Body:**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_password": "string"
}
```

---

## Request/Response Schemas

### User Schemas

```python
class UserBase(BaseModel):
    nom: str
    prenom: str
    departement: Optional[str]
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
    
    class Config:
        from_attributes = True
```

### Course Schemas

```python
class CourseBase(BaseModel):
    title: str
    description: str
    departement: str
    external_links: Optional[str]
    quiz_link: Optional[str]

class CourseMaterial(BaseModel):
    id: int
    course_id: int
    file_name: str
    file_path: str
    file_type: str
    file_category: str
    uploaded_at: datetime

class Course(CourseBase):
    id: int
    instructor_id: int
    created_at: datetime
    updated_at: datetime
    materials: List[CourseMaterial]
    instructor: dict
    image_url: Optional[str]
```

### Notification Schemas

```python
class Notification(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime
    related_course_id: Optional[int]
    related_material_id: Optional[int]

class NotificationResponse(BaseModel):
    notifications: List[Notification]
    unread_count: int
```

### Message Schemas

```python
class MessageInDB(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    file_path: Optional[str]
    file_type: Optional[str]
    is_read: bool
    created_at: datetime
    sender: UserMessage
    receiver: UserMessage
```

### Conference Schemas

```python
class ConferenceStatus(str, Enum):
    pending = "En attente"
    approved = "Approuvé"
    denied = "Refusé"

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
```

---

## Services

### Notification Service (`services/notification_service.py`)

Provides notification management functionality:

| Function | Description |
|----------|-------------|
| `create_notification()` | Create a new notification |
| `mark_notification_as_read()` | Mark notification as read |
| `get_user_notifications()` | Get all user notifications with unread count |
| `notify_new_account_request()` | Notify admin of new registration |
| `notify_course_request()` | Notify admin of course request |
| `notify_new_course()` | Notify admin of new course |
| `notify_professor_new_course()` | Notify professors of department course |
| `notify_employer_new_course()` | Notify employers of department course |
| `notify_conference_request()` | Notify admin of conference request |
| `notify_conference_status()` | Notify professor of conference status |
| `notify_course_deleted()` | Notify of course deletion |
| `notify_material_added()` | Notify of new material |
| `notify_course_progress()` | Notify of progress update |

### Message Service (`services/message_service.py`)

Provides messaging functionality:

| Function | Description |
|----------|-------------|
| `save_message_file()` | Save message attachment to filesystem |
| `create_message()` | Create and store a new message |
| `get_user_messages()` | Get received or sent messages |
| `get_message()` | Get specific message details |
| `mark_message_as_read()` | Mark message as read |
| `delete_message()` | Delete a message and its attachment |

---

## Utilities

### File Storage (`utils.py`)

```python
UPLOAD_DIR = "uploads"

def ensure_upload_dir():
    """Create uploads directory if not exists"""

def save_uploaded_file(file: UploadFile, course_id: int) -> str:
    """Save uploaded file to course-specific directory"""
```

### Cloudinary Integration

Images and videos are uploaded to Cloudinary:
- **Cloud Name**: plateforme
- **Folder Structure**: `courses/{course_id}/images/` and `courses/{course_id}/videos/`

PDF files are stored locally:
- **Location**: `uploads/pdfs/`
- **Served at**: `/pdfs/` endpoint

---

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database (Railway PostgreSQL)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=trolley.proxy.rlwy.net
POSTGRES_PORT=52911
POSTGRES_DB=railway

# Authentication
SECRET_KEY=your_secret_key_here

# Default Admin (optional)
DEFAULT_ADMIN_EMAIL=admin@gig.dz
DEFAULT_ADMIN_PASSWORD=admin123

# Cloudinary (optional, defaults provided)
CLOUDINARY_CLOUD_NAME=plateforme
CLOUDINARY_API_KEY=232349857927888
CLOUDINARY_API_SECRET=E2gxDYwCsXBCWbhx8oRN8e3Hmzo
```

### Database Configuration (`database.py`)

```python
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:juumdBVQjIAbBXjIqsQQSqRgVTFTsQpj@trolley.proxy.rlwy.net:52911/railway"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }
)
```

### CORS Configuration

CORS is enabled for all origins in development:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Deployment

### Prerequisites

- Python 3.9+
- PostgreSQL database
- Cloudinary account (optional)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Backend-main
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize database:
```bash
python init_db.py
```

6. Run the application:
```bash
uvicorn main:app --reload
```

### Production Deployment

For production, consider:
- Using a reverse proxy (nginx)
- Setting `allow_origins` to specific frontend domain
- Using environment variables for all secrets
- Enabling HTTPS
- Using a process manager (PM2, Supervisor)

### API Documentation

FastAPI automatically generates API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## License

Proprietary - Gulf Insurance Group (GIG) Algeria
