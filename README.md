# TAKWINI — Backend Documentation

Corporate Learning Management System (LMS) for Gulf Insurance Group (GIG) Algeria.
Built with FastAPI + PostgreSQL + Redis caching.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [User Roles](#user-roles)
5. [Database Models](#database-models)
6. [API Endpoints](#api-endpoints)
7. [Authentication](#authentication)
8. [File Storage](#file-storage)
9. [Caching System](#caching-system)
10. [Environment Setup](#environment-setup)
11. [Running Locally](#running-locally)
12. [Dependencies](#dependencies)
13. [Known Issues / TODO](#known-issues--todo)

---

## Project Overview

TAKWINI manages employee training inside GIG Algeria. It handles:
- Course creation and management with file uploads (image, PDF, video)
- Employee enrollment and progress tracking
- Internal messaging with file attachments
- Conference scheduling and approval
- Real-time notifications
- Role-based access control (admin, prof, employer)

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Web Framework | FastAPI | 0.115.5 |
| ASGI Server | Uvicorn | 0.32.0 |
| ORM | SQLAlchemy | 2.0.36 |
| Database | PostgreSQL | — |
| Validation | Pydantic | 2.12.5 |
| Cache | Redis (Upstash) | — |
| Redis Client | redis-py | 5.0.1 |
| Auth | python-jose + passlib | 3.3.0 / 1.7.4 |
| Password Hashing | bcrypt | 4.0.1 |
| Settings | pydantic-settings | 2.13.1 |
| File Uploads | python-multipart | 0.0.6 |

---

## Project Structure

```
Backend-main/
│
├── main.py                  # App factory, mounts all routers
├── auth.py                  # JWT creation, bcrypt hashing
├── database.py              # SQLAlchemy engine + session
├── config.py                # Settings loaded from .env
├── dependencies.py          # get_db, get_current_user, role guards
├── schemas.py               # All Pydantic input/output models
├── cache.py                 # Redis cache layer (all cache logic lives here)
│
├── models/
│   ├── base.py              # Declarative Base
│   ├── user.py              # User table
│   ├── course.py            # Course, CourseMaterial, CourseProgress
│   ├── notification.py      # Notification table
│   ├── message.py           # Message table
│   └── conference.py        # ConferenceRequest + ConferenceStatus enum
│
├── routers/
│   ├── auth.py              # POST /register, POST /token
│   ├── users.py             # Admin + profile + preferences + cache admin
│   ├── courses.py           # Course CRUD + file upload + cache
│   ├── enrollment.py        # Enroll, progress, complete
│   ├── notifications.py     # Get notifications, mark as read + cache
│   ├── messages.py          # Send, receive, delete messages
│   └── conferences.py       # Request, approve, calendar + cache
│
├── services/
│   ├── notification_service.py  # All notification logic + cache invalidation
│   ├── message_service.py       # Message CRUD
│   └── course_service.py        
│
├── uploads/                 # All local file storage
│   ├── courses/
│   │   └── {course_id}/
│   │       ├── images/
│   │       ├── pdfs/
│   │       └── videos/
│   └── messages/
│       └── {message_id}/
│
├── .env                     
├── requirements.txt
└── venv/
```

---

## User Roles

| Role | Description | Key Permissions |
|---|---|---|
| `admin` | HR / system administrator | Approves users, manages everything, approves conferences |
| `prof` | Trainers / instructors | Creates and manages courses, requests conferences |
| `employer` | Employees / learners | Enrolls in courses, tracks progress, sends messages |

Role strings in code are exactly: `"admin"`, `"prof"`, `"employer"`

---

## Database Models

### User
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| nom, prenom | str | First/last name |
| departement | str | Department |
| role | str | admin / prof / employer |
| email | str | Unique |
| telephone | str | |
| hashed_password | str | bcrypt |
| is_active | bool | Default True |
| is_approved | bool | Default False — admin must approve |
| language | str | fr / en |
| theme | str | light / dark |

### Course
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| title, description | str | |
| instructor_id | FK → User | |
| departement | str | |
| external_links, quiz_link | str | Optional |
| created_at, updated_at | datetime | |

### CourseMaterial
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| course_id | FK → Course | |
| file_name, file_path | str | Local path |
| file_type | str | MIME type |
| file_category | str | photo / material / record |

### CourseProgress
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| user_id, course_id | FK | |
| progress | float | 0.0 – 100.0 |
| status | str | En cours / Terminé |
| start_date, completion_date | datetime | |

### Notification
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| user_id | FK → User | |
| title, message | str | |
| type | str | See notification types below |
| is_read | bool | |
| related_course_id | FK nullable | |

### Message
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| sender_id, receiver_id | FK → User | |
| content | str | |
| file_path, file_type | str | Optional attachment |
| is_read | bool | |

### ConferenceRequest
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| name, description | str | |
| link | str | Optional |
| type | str | online / in-person |
| departement | str | |
| date | datetime | |
| time | str | HH:MM format |
| requested_by_id | FK → User | |
| status | enum | En attente / Approuvé / Refusé |

---

## API Endpoints

### Auth
| Method | Path | Description | Auth |
|---|---|---|---|
| POST | /register | Create account (is_approved=False) | None |
| POST | /token | Login, returns JWT | None |

### Users — Admin
| Method | Path | Description |
|---|---|---|
| GET | /admin/pending-users | List unapproved users |
| POST | /admin/approve-user/{id} | Approve or reject user |
| DELETE | /admin/users/{id} | Delete user |
| PUT | /admin/users/{id} | Update user info |
| GET | /admin/cache-stats | Redis cache metrics |
| DELETE | /admin/cache-clear | Wipe entire cache |

### Users — Any Authenticated
| Method | Path | Description |
|---|---|---|
| GET | /public/users | All users (for messaging UI) |
| GET | /personal-info | Get telephone |
| PUT | /personal-info | Update telephone |
| GET | /preferences | Get language + theme |
| PUT | /preferences | Update language / theme |
| PUT | /password | Change password |

### Courses
| Method | Path | Description | Cache |
|---|---|---|---|
| GET | /courses/ | List courses | ✅ 2 min TTL |
| GET | /courses/by-department | Courses by current user dept | ✅ 2 min TTL |
| GET | /courses/{id} | Single course with materials | ✅ 3 min TTL |
| GET | /courses/{id}/materials/ | List materials | ❌ |
| POST | /courses/ | Create course (prof/admin) | Invalidates list |
| PUT | /courses/{id} | Update course metadata | Invalidates detail + list |
| DELETE | /courses/{id} | Delete course + local files | Invalidates detail + list |
| DELETE | /courses/{id}/materials/{mid} | Delete material | ❌ |

### Enrollment & Progress
| Method | Path | Description |
|---|---|---|
| POST | /courses/{id}/enroll | Enroll in course |
| GET | /courses/{id}/progress | Get progress |
| PUT | /courses/{id}/progress?progress_value=75 | Update progress (0–100) |
| PUT | /courses/{id}/complete | Force complete |

### Notifications
| Method | Path | Description | Cache |
|---|---|---|---|
| GET | /notifications/ | All notifications + unread count | ✅ 30 sec TTL |
| PUT | /notifications/{id}/read | Mark as read | Invalidates user cache |

### Messages
| Method | Path | Description |
|---|---|---|
| POST | /messages/ | Send message (multipart: content, receiver_id, optional file) |
| GET | /messages/?message_type=received | Get messages |
| GET | /messages/{id} | Get + auto-mark as read |
| PUT | /messages/{id}/read | Explicit mark as read |
| DELETE | /messages/{id} | Delete message + file |
| GET | /messages/file/{id} | Download attachment |

### Conferences
| Method | Path | Description | Cache |
|---|---|---|---|
| POST | /request | Create conference request | Invalidates calendar if admin |
| GET | /admin/pending-conferences | List pending (admin only) | ❌ real-time |
| PUT | /admin/approve/{id}?approve=true | Approve or deny | Invalidates calendar |
| GET | /prof/my-conferences | Professor's own requests | ❌ real-time |
| GET | /calendar | Approved conferences | ✅ 5 min TTL |
| GET | /conferences/{id} | Single conference | ❌ |
| DELETE | /conferences/{name} | Delete by name (owner only) | Invalidates calendar |

---

## Authentication

1. `POST /token` accepts OAuth2 form data (email + password)
2. Verifies bcrypt password hash
3. Checks `is_approved == True`
4. Returns JWT (HS256, 30 min expiry)
5. Every protected route reads `Authorization: Bearer <token>` header
6. `get_current_user()` decodes JWT and loads user from DB
7. Role guards check `current_user.role`

---

## File Storage

All files are stored locally. No external storage service.

```
Course image  → uploads/courses/{course_id}/images/{filename}
Course PDF    → uploads/courses/{course_id}/pdfs/{filename}
Course video  → uploads/courses/{course_id}/videos/{filename}
Message files → uploads/messages/{message_id}/{timestamp}_{filename}
```

Served via FastAPI `StaticFiles` mounted at `/uploads`.
When a course is deleted, the entire `uploads/courses/{course_id}/` folder is removed.

---

## Caching System

### Overview

Redis-based caching via [Upstash](https://upstash.com) (serverless Redis, works with any hosting).
All cache logic lives in `cache.py`. Safe fallback — if Redis is unreachable, the API continues working normally with DB queries only.

### Cache Keys

| Key Pattern | TTL | Invalidated When |
|---|---|---|
| `courses:list:all` | 120s | Course created / updated / deleted |
| `courses:list:dept:{dept}` | 120s | Course created / updated / deleted |
| `courses:detail:{id}` | 180s | Course updated / deleted |
| `notifications:user:{id}` | 30s | Notification created / marked as read |
| `conferences:calendar:all` | 300s | Conference approved / deleted |
| `conferences:calendar:dept:{dept}` | 300s | Conference approved / deleted |

### Performance Results

| Endpoint | Before Cache | After Cache | Improvement |
|---|---|---|---|
| GET /courses/ | 107ms | 54ms | 50% |
| GET /notifications/ | 277ms | 63ms | 77% |
| GET /calendar | 169ms | 69ms | 59% |

### Admin Cache Endpoints

```
GET  /admin/cache-stats   → Returns Redis memory, hit/miss ratio, connected clients
DELETE /admin/cache-clear → Wipes entire cache (use when data feels stale after DB changes)
```

### `cache.py` Public API

```python
cache_get(key)                        # Returns cached value or None
cache_set(key, value, ttl)            # Stores value with TTL in seconds
cache_delete(key)                     # Deletes single key
cache_delete_pattern(prefix)          # Deletes all keys starting with prefix
cache_stats()                         # Returns Redis info dict
```

### TTL Constants

```python
TTL_COURSES_LIST  = 120   # 2 min
TTL_COURSE_DETAIL = 180   # 3 min
TTL_NOTIFICATIONS = 30    # 30 sec
TTL_CALENDAR      = 300   # 5 min
```

---

## Environment Setup

### `.env` file

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/takwini
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEFAULT_ADMIN_EMAIL=admin@gig.dz
DEFAULT_ADMIN_PASSWORD=admin123
UPLOAD_DIR=uploads
REDIS_URL=rediss://default:password@your-endpoint.upstash.io:6379
```

### `config.py` Settings

```python
class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    default_admin_email: str = "admin@gig.dz"
    default_admin_password: str = "admin123"
    upload_dir: str = "uploads"
    redis_url: str = ""
```

---

## Running Locally

```bash
# 1. Clone the repo and enter the folder
cd Backend-main

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file with your values (see Environment Setup above)

# 5. Create PostgreSQL database named: takwini

# 6. Run the server
uvicorn main:app --reload

# 7. Open API docs
http://localhost:8000/docs
```

---

## Dependencies

```txt
fastapi==0.115.5
starlette==0.41.3
uvicorn==0.32.0
python-dotenv==1.0.0
sqlalchemy==2.0.36
pydantic==2.12.5
pydantic-settings==2.13.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
python-multipart==0.0.6
email-validator==2.3.0
psycopg2-binary==2.9.11
redis==5.0.1
```

### Why these exact versions

| Package | Reason |
|---|---|
| `fastapi==0.115.5` | Minimum version that supports Pydantic 2.12.x |
| `starlette==0.41.3` | Exact version required by fastapi 0.115.5 |
| `sqlalchemy==2.0.36` | Minimum version compatible with Python 3.13 |
| `bcrypt==4.0.1` | bcrypt 5.x breaks passlib's verify() method |
| `pydantic==2.12.5` | Latest stable, all schemas use ConfigDict |

---

## Notification Types

| Type | Triggered When |
|---|---|
| `account_request` | New user registers |
| `account_approval` | Admin approves/rejects account |
| `new_course` | Course created (notifies admin) |
| `department_new_course` | Course created (notifies profs in dept) |
| `new_course_available` | Course created (notifies employers in dept) |
| `course_deleted` | Course deleted (notifies admin) |
| `material_added` | Material added to course |
| `progress_updated` | User updates their progress |
| `conference_request` | Prof requests a conference (notifies admin) |
| `conference_status` | Admin approves/denies conference (notifies prof) |

---

## Known Issues / TODO

1. `dashboard/employer` endpoint missing department filter (bug)
2. No `/users/me` endpoint with statistics
3. No real-time notifications — currently DB polling, SSE planned
4. CORS set to `localhost:3000` — update to real frontend URL before production
5. No token refresh mechanism — users are logged out after 30 min
6. No token blacklist — logout does not invalidate the token server-side
7. Messages endpoint has no cache — can be added following the same pattern as notifications
