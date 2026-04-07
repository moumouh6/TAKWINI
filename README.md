# TAKWINI Backend

> Corporate Learning Management System for Gulf Insurance Group (GIG) Algeria  
> FastAPI · PostgreSQL · Redis · Python 3.13

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [User Roles & Access Control](#user-roles--access-control)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Caching Strategy](#caching-strategy)
- [File Storage](#file-storage)
- [Notification System](#notification-system)
- [Dependency Decisions](#dependency-decisions)
- [Deployment](#deployment)
- [Known Issues & Roadmap](#known-issues--roadmap)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Client                           │
│              (React Frontend / Mobile App)              │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (Uvicorn)                     │
│                                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│   │  /auth   │  │ /courses │  │   /notifications     │ │
│   │ /users   │  │ /enroll  │  │   /messages          │ │
│   └──────────┘  └──────────┘  │   /conferences       │ │
│                                └──────────────────────┘ │
│                                                         │
│   ┌──────────────────────┐  ┌───────────────────────┐  │
│   │      cache.py        │  │  notification_service │  │
│   │    (Redis layer)     │  │  message_service      │  │
│   └──────────┬───────────┘  └───────────────────────┘  │
└──────────────┼──────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────────┐
│  PostgreSQL │  │  Redis (Upstash) │
│  (primary)  │  │  (cache layer)   │
└─────────────┘  └──────────────────┘
```

**Request flow for a cached endpoint:**
1. Request hits FastAPI router
2. Router checks Redis → **cache hit: return in ~2ms**
3. Cache miss → query PostgreSQL → serialize → store in Redis → return
4. On write (create/update/delete) → invalidate relevant cache keys immediately

---

## Quick Start

### Option 1: Docker (Easiest - Recommended for Demo)

```bash
# 1. Copy the Docker environment file
cp .env.docker .env

# 2. Start everything (PostgreSQL + API)
docker-compose up -d

# 3. That's it! Access the API at:
#    http://localhost:8000/docs
```

### Option 2: Local Development

**Prerequisites:** Python 3.13+, PostgreSQL 14+

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 4. Create database
createdb takwini

# 5. Run
uvicorn main:app --reload

# API docs: http://localhost:8000/docs
```

---

## Environment Variables

Create a `.env` file in the project root. **Never commit this file.**

```env
# ── Database ──────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/takwini

# ── JWT Auth ──────────────────────────────────────────────────
SECRET_KEY=change-this-to-a-long-random-string-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── Default Admin Account (created on first run) ──────────────
DEFAULT_ADMIN_EMAIL=admin@gig.dz
DEFAULT_ADMIN_PASSWORD=change-this-in-production

# ── File Storage ──────────────────────────────────────────────
UPLOAD_DIR=uploads

# ── Redis Cache (Upstash) ─────────────────────────────────────
REDIS_URL=rediss://default:yourpassword@your-endpoint.upstash.io:6379
```

> **Generate a secure SECRET_KEY:**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Project Structure

```
Backend-main/
│
├── main.py                      # App factory, router registration, static files
├── auth.py                      # JWT encode/decode, bcrypt hash/verify
├── database.py                  # SQLAlchemy engine, session factory
├── config.py                    # Pydantic settings, reads from .env
├── dependencies.py              # FastAPI dependencies: get_db, get_current_user,
│                                #   require_admin, require_prof_or_admin, require_approved
├── schemas.py                   # All Pydantic v2 request/response models
├── cache.py                     # Redis cache layer — all caching logic lives here
│
├── models/
│   ├── base.py
│   ├── user.py
│   ├── course.py                # Course, CourseMaterial, CourseProgress
│   ├── notification.py
│   ├── message.py
│   └── conference.py            # ConferenceRequest, ConferenceStatus enum
│
├── routers/
│   ├── auth.py                  # POST /register  POST /token
│   ├── users.py                 # User management, preferences, cache admin endpoints
│   ├── courses.py               # Course CRUD + file upload + cache
│   ├── enrollment.py            # Enroll, progress tracking
│   ├── notifications.py         # Fetch + mark as read + cache
│   ├── messages.py              # Internal messaging
│   └── conferences.py           # Conference requests + calendar + cache
│
├── services/
│   ├── notification_service.py  # Notification creation + cache invalidation on notify
│   ├── message_service.py       # Message CRUD helpers
│   └── course_service.py        # (placeholder, mostly unused)
│
├── uploads/                     # Local file storage — gitignored
│   ├── courses/{id}/images/
│   ├── courses/{id}/pdfs/
│   ├── courses/{id}/videos/
│   └── messages/{id}/
│
├── .env                         # Secret config — NEVER commit
├── .env.example                 # Safe template — commit this
├── .gitignore
└── requirements.txt
```

---

## User Roles & Access Control

Three roles, enforced via FastAPI dependency injection on every protected route.

| Role | Code Value | Description |
|---|---|---|
| Administrator | `"admin"` | Full access. Approves users, manages all content, approves conferences. |
| Instructor | `"prof"` | Creates and manages courses. Requests conferences. |
| Employee | `"employer"` | Enrolls in courses, tracks own progress, sends messages. Scoped to their department. |

### Role Guards

```python
require_admin            # role == "admin" only
require_prof_or_admin    # role in ("prof", "admin")
require_approved         # is_approved == True, any role
get_current_user         # any valid JWT
```

> `employer` users only see courses and conferences from their own `departement`. This filter is applied at the query level — not in the response.

---

## Database Schema

### Users

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| nom / prenom | VARCHAR | Last / first name |
| departement | VARCHAR | |
| role | VARCHAR | `admin` / `prof` / `employer` |
| email | VARCHAR UNIQUE | |
| telephone | VARCHAR | |
| hashed_password | VARCHAR | bcrypt |
| is_active | BOOLEAN | DEFAULT TRUE |
| is_approved | BOOLEAN | DEFAULT FALSE — admin must flip |
| language | VARCHAR | `fr` / `en` |
| theme | VARCHAR | `light` / `dark` |
| created_at | TIMESTAMP | |

### Courses

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| title / description | VARCHAR / TEXT | |
| instructor_id | FK → users.id | |
| departement | VARCHAR | Scopes employer visibility |
| external_links / quiz_link | TEXT | Optional |
| created_at / updated_at | TIMESTAMP | |

### CourseMaterials

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| course_id | FK → courses.id | |
| file_name / file_path | VARCHAR | Sanitized name, local path |
| file_type | VARCHAR | MIME type |
| file_category | VARCHAR | `photo` / `material` / `record` |
| uploaded_at | TIMESTAMP | |

### CourseProgress

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id / course_id | FK | |
| progress | FLOAT | 0.0 – 100.0 |
| status | VARCHAR | `En cours` / `Terminé` |
| start_date | TIMESTAMP | Set on enroll |
| completion_date | TIMESTAMP | Set when complete |
| is_completed | BOOLEAN | |

### Notifications

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | FK → users.id | |
| title / message | VARCHAR / TEXT | |
| type | VARCHAR | See Notification Types |
| is_read | BOOLEAN | DEFAULT FALSE |
| related_course_id | FK nullable | |
| created_at | TIMESTAMP | |

### Messages

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| sender_id / receiver_id | FK → users.id | |
| content | TEXT | |
| file_path / file_type | VARCHAR | Nullable attachment |
| is_read | BOOLEAN | DEFAULT FALSE |
| created_at | TIMESTAMP | |

### ConferenceRequests

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name / description | VARCHAR / TEXT | |
| link | VARCHAR | Nullable, for online conferences |
| type | VARCHAR | `online` / `in-person` |
| departement | VARCHAR | |
| date | TIMESTAMP | |
| time | VARCHAR | HH:MM |
| requested_by_id | FK → users.id | |
| status | ENUM | `En attente` / `Approuvé` / `Refusé` |
| created_at | TIMESTAMP | |

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/register` | None | Register. Account pending until admin approves. |
| POST | `/token` | None | OAuth2 form (email + password). Returns JWT. |

### User Management

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/pending-users` | admin | List unapproved accounts |
| POST | `/admin/approve-user/{id}` | admin | Approve or reject `{ is_approved: bool }` |
| DELETE | `/admin/users/{id}` | admin | Hard delete user |
| PUT | `/admin/users/{id}` | admin | Update any user |
| GET | `/public/users` | none | All users — used by messaging UI |
| GET | `/personal-info` | any | Own telephone |
| PUT | `/personal-info` | any | Update telephone |
| GET | `/preferences` | any | Own language + theme |
| PUT | `/preferences` | any | Update language or theme |
| PUT | `/password` | any | Change password (requires current password) |

### Courses

| Method | Path | Auth | Cache | Description |
|---|---|---|---|---|
| GET | `/courses/` | approved | ✅ 2 min | List. Employers scoped to dept. |
| GET | `/courses/by-department` | approved | ✅ 2 min | Current user's department only. |
| GET | `/courses/{id}` | approved | ✅ 3 min | Single course with materials + instructor. |
| GET | `/courses/{id}/materials/` | approved | ❌ | List materials. |
| POST | `/courses/` | prof/admin | Invalidates list | Multipart: title, desc, dept, image, pdf, optional video. |
| PUT | `/courses/{id}` | prof/admin | Invalidates detail + list | Update metadata only. |
| DELETE | `/courses/{id}` | prof/admin | Invalidates detail + list | Deletes DB record + all local files. |
| DELETE | `/courses/{id}/materials/{mid}` | prof/admin | ❌ | Delete one material. |

### Enrollment & Progress

| Method | Path | Description |
|---|---|---|
| POST | `/courses/{id}/enroll` | Enroll. Creates progress record at `En cours`. |
| GET | `/courses/{id}/progress` | Get own progress. |
| PUT | `/courses/{id}/progress?progress_value=75` | Update progress 0–100. |
| PUT | `/courses/{id}/complete` | Force-complete. |

### Notifications

| Method | Path | Cache | Description |
|---|---|---|---|
| GET | `/notifications/` | ✅ 30 sec | All notifications + unread count. |
| PUT | `/notifications/{id}/read` | Invalidates user | Mark as read. |

### Messages

| Method | Path | Description |
|---|---|---|
| POST | `/messages/` | Send. Multipart: `content`, `receiver_id`, optional file. |
| GET | `/messages/?message_type=received` | Fetch received or sent. |
| GET | `/messages/{id}` | Fetch single. Auto-marks as read. |
| PUT | `/messages/{id}/read` | Explicit mark as read. |
| DELETE | `/messages/{id}` | Delete message + file. |
| GET | `/messages/file/{id}` | Download attachment (FileResponse). |

### Conferences

| Method | Path | Auth | Cache | Description |
|---|---|---|---|---|
| POST | `/request` | prof/admin | Invalidates calendar if admin | Create. Admin requests auto-approved. |
| GET | `/admin/pending-conferences` | admin | ❌ real-time | All pending requests. |
| PUT | `/admin/approve/{id}?approve=true` | admin | Invalidates calendar | Approve or deny. |
| GET | `/prof/my-conferences` | prof | ❌ real-time | Own requests. |
| GET | `/calendar` | any | ✅ 5 min | Approved conferences. Employers scoped to dept. |
| GET | `/conferences/{id}` | any | ❌ | Single conference. |
| DELETE | `/conferences/{name}` | owner | Invalidates calendar | Delete by name. |

### Cache Management (Admin Only)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/cache-stats` | Live Redis metrics: memory, hit/miss ratio, clients. |
| DELETE | `/admin/cache-clear` | Wipe entire Redis DB. Emergency use only. |

---

## Authentication

TAKWINI uses **JWT Bearer tokens** via OAuth2 password flow.

```
POST /token
  body: username=email&password=plain   (form-encoded)
  → verify bcrypt hash
  → check is_approved == True
  → return { access_token, token_type: "bearer" }

Protected routes:
  Header: Authorization: Bearer <token>
  → decode JWT (HS256)
  → load User from DB
  → apply role guard
```

| Property | Value |
|---|---|
| Algorithm | HS256 |
| Expiry | 30 minutes (configurable via env) |
| Payload | `{ sub: email, exp: timestamp }` |
| Refresh token | Not implemented — see Roadmap |
| Blacklist | Not implemented — see Roadmap |

> Logout on the client side simply discards the token. The token remains technically valid until expiry. Acceptable for internal corporate use; add a Redis-based blacklist before any public deployment.

---

## Caching Strategy

### Why Redis over in-memory

In-memory dicts work for single-process dev but break under multiple Uvicorn workers — each process holds its own cache and they diverge. Redis is a shared external store; all workers read and write the same data. With 100–500 users on production, Redis is the correct choice.

We use **[Upstash](https://upstash.com)** — serverless Redis accessed via a connection URL. No server to manage. Works with Render, Railway, any VPS, or local dev. Free tier covers ~10,000 requests/day.

### Fallback Behavior

Every function in `cache.py` is wrapped in try/except. If Upstash is unreachable at startup or during a request, the API silently falls back to direct DB queries. No crash, no stale data, no data loss.

### Cache Keys & TTLs

| Key | TTL | Description |
|---|---|---|
| `courses:list:all` | 120s | All courses (admin / prof view) |
| `courses:list:dept:{dept}` | 120s | Dept-filtered list (employer view) |
| `courses:detail:{id}` | 180s | Single course with materials + instructor |
| `notifications:user:{id}` | 30s | Per-user notification list + unread count |
| `conferences:calendar:all` | 300s | Full approved calendar |
| `conferences:calendar:dept:{dept}` | 300s | Dept-filtered calendar |

### Invalidation Map

| Trigger | Invalidates |
|---|---|
| Course created | `courses:list:*` |
| Course updated | `courses:detail:{id}`, `courses:list:*` |
| Course deleted | `courses:detail:{id}`, `courses:list:*` |
| Notification created (single) | `notifications:user:{user_id}` |
| Notification created (bulk) | `notifications:user:{id}` for every recipient |
| Notification marked as read | `notifications:user:{user_id}` |
| Conference approved / denied | `conferences:calendar:*` |
| Conference deleted | `conferences:calendar:*` |

Pattern deletion uses `SCAN` — not `KEYS`. `KEYS` blocks Redis on large datasets. `SCAN` is cursor-based and non-blocking. Safe in production.

### Measured Performance

| Endpoint | Without Cache | With Cache | Gain |
|---|---|---|---|
| `GET /courses/` | 107ms | 54ms | **50%** |
| `GET /notifications/` | 277ms | 63ms | **77%** |
| `GET /calendar` | 169ms | 69ms | **59%** |

Notifications showed the biggest gain because the endpoint runs two queries (full list + unread count). Both are eliminated on cache hit.

### Monitoring

```bash
GET  /admin/cache-stats    # memory, hit/miss, connected clients
DELETE /admin/cache-clear  # wipe all keys — use after direct DB patches
```

Sample response:
```json
{
  "status": "connected",
  "used_memory_human": "1.45M",
  "connected_clients": 1,
  "total_commands_processed": 842,
  "keyspace_hits": 631,
  "keyspace_misses": 94
}
```

Target hit rate in production: **> 70%**  
Formula: `keyspace_hits / (keyspace_hits + keyspace_misses)`

---

## File Storage

All uploads are stored on the local filesystem. Cloudinary was removed.

### Directory Layout

```
uploads/
├── courses/
│   └── {course_id}/
│       ├── images/      ← thumbnail (required on create)
│       ├── pdfs/        ← course material (required on create)
│       └── videos/      ← course video (optional)
└── messages/
    └── {message_id}/
        └── {timestamp}_{filename}
```

### Filename Sanitization

```python
re.sub(r'[^A-Za-z0-9_.-]', '_', filename)
```

Strips all non-safe characters before saving. Prevents path traversal and encoding issues.

### Serving

Files are served via FastAPI `StaticFiles` mounted at `/uploads`. No per-request auth on the URL itself — security relies on the frontend not exposing raw paths to unauthorized users.

> For public-facing deployments: serve through a CDN or add an authenticated proxy endpoint.

### Cleanup

Course deletion calls `shutil.rmtree(f"uploads/courses/{course_id}")` atomically with the DB delete. No orphaned files.

---

## Notification System

### Two Creation Paths

```python
# Single user — 1 DB commit
create_notification(db, user_id, title, message, type, course_id)

# Multiple users — 1 DB commit via bulk_save_objects
_bulk_notify(db, user_ids, title, message, type, course_id)
```

`bulk_save_objects` matters at scale. Creating a course that notifies 200 employees = 1 DB commit, not 200.

Both paths call `cache_delete(f"notifications:user:{user_id}")` after committing, ensuring the next fetch always reflects current state.

### Notification Types

| Type | Recipient | Trigger |
|---|---|---|
| `account_request` | Admin | New user registers |
| `account_approval` | User | Admin approves / rejects account |
| `new_course` | Admin | Any course created |
| `department_new_course` | All profs in dept | Course created in their dept |
| `new_course_available` | All employers in dept | Course created in their dept |
| `course_deleted` | Admin | Course deleted |
| `material_added` | Admin + enrolled users | Material added to a course |
| `progress_updated` | User | Own progress updated |
| `conference_request` | Admin | Prof submits a conference request |
| `conference_status` | Prof | Admin approves / denies their request |

---

## Docker Deployment

For testing and demo purposes, use Docker Compose:

```bash
# 1. Start PostgreSQL + API
docker-compose up -d

# 2. Check logs
docker-compose logs -f

# 3. Stop
docker-compose down

# 4. Stop and remove data (fresh start)
docker-compose down -v
```

**Services:**
- API: http://localhost:8000/docs
- PostgreSQL: localhost:5432 (user: `takwini`, pass: `takwini123`)

**Files:**
- `Dockerfile` — Container definition
- `docker-compose.yml` — Services configuration
- `.env.docker` — Environment template (already configured for Docker)

---

## Dependency Decisions

Every version is pinned deliberately. Do not upgrade without reading the reason.

| Package | Version | Reason |
|---|---|---|
| `fastapi` | 0.115.5 | Minimum version compatible with Pydantic 2.12.x. Earlier versions crash with `AttributeError: 'FieldInfo' object has no attribute 'in_'` on Python 3.13. |
| `starlette` | 0.41.3 | Exact peer dependency of fastapi 0.115.5. Do not change independently. |
| `uvicorn` | 0.32.0 | Compatible with starlette 0.41.x. |
| `sqlalchemy` | 2.0.36 | Minimum for Python 3.13. Version 2.0.23 fails with `AssertionError` on `__firstlineno__` / `__static_attributes__`. |
| `pydantic` | 2.12.5 | Latest stable. All schemas use `model_config = ConfigDict(from_attributes=True)`. |
| `pydantic-settings` | 2.13.1 | Matched to pydantic 2.12.x. |
| `bcrypt` | 4.0.1 | bcrypt 5.x enforces a 72-byte password limit that raises `ValueError` inside `passlib.verify()`. |
| `passlib[bcrypt]` | 1.7.4 | Last stable release, no longer maintained. Acceptable for internal use. |
| `python-jose[cryptography]` | 3.3.0 | JWT with cryptography backend. |
| `redis` | 5.0.1 | Stable client for Redis 7.x and Upstash. |
| `email-validator` | 2.3.0 | Required by `pydantic[email]` for `EmailStr` fields. |
| `psycopg2-binary` | 2.9.11 | PostgreSQL adapter. Binary avoids compilation. |

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

---

## Deployment

### Pre-Deploy Checklist

- [ ] Generate a new `SECRET_KEY` — never use the dev value in production
- [ ] Change `DEFAULT_ADMIN_PASSWORD` to something strong
- [ ] Update CORS origin in `main.py` from `localhost:3000` to your real frontend URL
- [ ] Set `REDIS_URL` to your Upstash production database URL
- [ ] Set `DATABASE_URL` to your production PostgreSQL connection string
- [ ] Ensure `uploads/` is writable — mount a persistent volume if on Render/Railway
- [ ] Review `ACCESS_TOKEN_EXPIRE_MINUTES` — 30 min is reasonable

### Render / Railway

```
Build command : pip install -r requirements.txt
Start command : uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set all `.env` values in the platform's environment variables panel.  
`REDIS_URL` comes from your Upstash dashboard and works with any platform.

### Multiple Workers

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Works correctly because the cache is Redis (shared), not in-memory.  
With multiple workers and local file uploads, all workers must share the same filesystem. On Render, mount a persistent disk at the `uploads/` path.

---

## Known Issues & Roadmap

### Active Bugs

| Issue | File | Impact |
|---|---|---|
| Employer dashboard missing dept filter | `routers/enrollment.py` | Employers may see cross-dept data |

### Security Gaps

Acceptable for internal corporate use. Fix before any public-facing launch.

| Issue | Risk | Recommended Fix |
|---|---|---|
| No token refresh | Users re-login every 30 min | Refresh token endpoint + httpOnly cookie |
| No token blacklist | Logout doesn't invalidate server-side | Redis-based blacklist keyed on `jti` |
| Static files unprotected | Direct `/uploads/` URLs work without auth | Authenticated proxy endpoint |

### Planned Features

| Feature | Priority | Notes |
|---|---|---|
| `GET /users/me` with stats | Medium | Enrolled courses, completion rate, last active |
| Real-time notifications | Medium | Replace DB polling with SSE (Server-Sent Events) |
| Message caching | Low | Same pattern as notifications — per-user Redis key |
| Token refresh endpoint | High | Needed before production launch |
| Rate limiting on `/token` | High | Use `slowapi` to block brute force |
| Soft delete | Low | `deleted_at` column instead of hard deletes |
