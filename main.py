from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import timedelta, datetime
from typing import Annotated, List, Optional
import json
import os
import logging
from fastapi.responses import FileResponse
import sqlalchemy.orm
from fastapi.staticfiles import StaticFiles
from database import get_db, engine
from models.user import User, Base
from models.conference import ConferenceRequest 
from models.course import Course, CourseMaterial, CourseProgress
from schemas import (
    UserCreate, User as UserSchema, Token,
    CourseCreate, Course as CourseSchema,
    CourseMaterial as CourseMaterialSchema,
    UserApproval, PendingUser, Notification,
    NotificationResponse, MessageCreate, MessageInDB,
    ConferenceRequestCreate, ConferenceRequestOut, ConferenceStatus,
    UserSettings, UserSettingsUpdate, UserProfileUpdate, PasswordUpdate,
    UserSettingsResponse, UserPreferences, UserPreferencesUpdate,
    UserPersonalInfo, UserPersonalInfoUpdate, CourseBase
)
import shutil
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM
)
from jose import JWTError, jwt
from utils import save_uploaded_file
from services.notification_service import (
    notify_course_created,
    notify_course_deleted,
    notify_material_added,
    notify_course_progress,
    get_user_notifications,
    mark_notification_as_read,
    notify_new_course,
    notify_professor_new_course,
    notify_employer_new_course,
    notify_conference_request,
    notify_conference_status,
    create_notification
)
from services.message_service import (
    create_message,
    get_user_messages,
    get_message,
    mark_message_as_read,
    delete_message
)
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api
import re


CLOUDINARY_CLOUD_NAME="plateforme"
CLOUDINARY_API_KEY="232349857927888"
CLOUDINARY_API_SECRET="E2gxDYwCsXBCWbhx8oRN8e3Hmzo"


cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)


# Create database tables
Base.metadata.create_all(bind=engine)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utility function to clean filenames

def clean_filename(filename):
    """Remplace les espaces et caractères spéciaux par des underscores."""
    return re.sub(r'[^A-Za-z0-9_.-]', '_', filename)

def create_default_admin():
    """Creates a default admin user if it doesn't already exist."""
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@gig.dz")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    try:
        with next(get_db()) as db:
            admin = db.query(User).filter(User.email == admin_email).first()
            if not admin:
                admin_user = User(
                    nom="Admin",
                    prenom="System",
                    departement="RH",
                    role="admin",
                    email=admin_email,
                    telephone="0000000000",
                    hashed_password=get_password_hash(admin_password),
                    is_active=True,
                    is_approved=True
                )
                db.add(admin_user)
                db.commit()
                logger.info(f"✔ Default admin account created successfully with email: {admin_email}")
            else:
                logger.info(f"✓ Default admin account already exists with email: {admin_email}")
    except SQLAlchemyError as e:
        logger.error(f"Database error while creating default admin: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while creating default admin: {e}")

# Create default admin on startup
create_default_admin()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# At the top-level (after app = FastAPI())
app.mount("/pdfs", StaticFiles(directory="uploads/pdfs"), name="pdfs")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
):
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

# Middleware to check if user is a professor or admin
def verify_professor_or_admin(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.role not in ["prof", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only professors and administrators can perform this action"
        )
    return current_user

@app.post("/register", response_model=UserSchema)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if passwords match
    if user.password != user.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Check if email already exists
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        nom=user.nom,
        prenom=user.prenom,
        departement=user.departement,
        role=user.role,
        email=user.email,
        telephone=user.telephone,
        hashed_password=hashed_password,
        is_active=True,
        is_approved=False  # New users are not approved by default
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/admin/pending-users", response_model=List[PendingUser])
def get_pending_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Check if current user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can view pending users"
        )
    
    pending_users = db.query(User).filter(User.is_approved == False).all()
    return pending_users

@app.post("/admin/approve-user/{user_id}", response_model=UserSchema)
def approve_user(
    user_id: int,
    approval: UserApproval,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Check if current user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can approve users"
        )
    
    # Get the user to approve
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update approval status
    user.is_approved = approval.is_approved
    db.commit()
    db.refresh(user)
    return user


@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Check if current user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete users"
        )
    
    # Get the user to delete
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot delete their own account"
        )
    
    # Delete the user
    db.delete(user)
    db.commit()
    return None


@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is approved
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not approved yet. Please wait for admin approval.",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Get user's course progress
    progress_records = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id
    ).all()
    
    # Calculate statistics
    total_courses = len(progress_records)
    completed_courses = sum(1 for p in progress_records if p.is_completed)
    average_progress = sum(p.progress for p in progress_records) / total_courses if total_courses > 0 else 0
    
    # Calculate average completion time for completed courses
    completion_times = [(p.completion_date - p.start_date).days 
                       for p in progress_records 
                       if p.is_completed and p.completion_date]
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    return {
        "profile": {
            "nom": current_user.nom,
            "prenom": current_user.prenom,
            "email": current_user.email,
            "telephone": current_user.telephone,
            "departement": current_user.departement,
            "fonction": current_user.role
        },
        "statistics": {
            "total_cours_suivis": total_courses,
            "cours_termines": completed_courses,
            "progression_moyenne": f"{average_progress:.1f}%",
            "temps_moyen_completion": f"{avg_completion_time:.1f} jours"
        },
        "courses": [
            {
                "nom_du_cours": progress.course.title if progress.course else "Cours inconnu",
                "progres": f"{progress.progress:.1f}%",
                "date_debut": progress.start_date.strftime("%d/%m/%Y"),
                "date_fin": progress.completion_date.strftime("%d/%m/%Y") if progress.completion_date else "En cours...",
                "dernier_acces": progress.last_accessed.strftime("%d/%m/%Y %H:%M"),
                "statut": progress.status,
                "duree": f"{(datetime.utcnow() - progress.start_date).days} jours"
            }
            for progress in progress_records
        ]
    }

# Course endpoints
@app.post("/courses/", response_model=CourseSchema)
def upload_course(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(...),
    departement: str = Form(...),
    course_image: UploadFile = File(...),
    course_pdf: UploadFile = File(...),
    external_links: str = Form(None),
    quiz_link: str = Form(None),
    course_video: UploadFile = File(None)
):
    # 1. Créer le cours
    course = Course(
        title=title,
        description=description,
        instructor_id=current_user.id,
        departement=departement,
        external_links=external_links,
        quiz_link=quiz_link,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    materials = []

    # 2. Uploader l'image du cours sur Cloudinary
    course_image.file.seek(0)
    image_upload_result = cloudinary.uploader.upload(
        course_image.file.read(),
        resource_type="image",
        folder=f"courses/{course.id}/images",
        public_id=f"{course.id}_image_{course_image.filename}"
    )
    image_url = image_upload_result.get("secure_url")

    image_material = CourseMaterial(
        course_id=course.id,
        file_name=course_image.filename,
        file_path=image_url,
        file_type=course_image.content_type,
        file_category="photo"
    )
    db.add(image_material)
    materials.append(image_material)

    # 3. Save the PDF locally instead of uploading to Cloudinary
    pdf_folder = "uploads/pdfs"
    os.makedirs(pdf_folder, exist_ok=True)
    pdf_filename = clean_filename(course_pdf.filename)
    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # Chemin absolu à stocker
    absolute_pdf_path = os.path.abspath(pdf_path)

    course_pdf.file.seek(0)
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(course_pdf.file, buffer)

    pdf_material = CourseMaterial(
        course_id=course.id,
        file_name=course_pdf.filename,
        file_path=absolute_pdf_path,  # Chemin absolu
        file_type=course_pdf.content_type,
        file_category="material"
    )
    db.add(pdf_material)
    materials.append(pdf_material)

    # 4. Uploader la vidéo sur Cloudinary (si fournie)
    if course_video:
        course_video.file.seek(0)
        video_upload_result = cloudinary.uploader.upload(
            course_video.file.read(),
            resource_type="video",
            folder=f"courses/{course.id}/videos",
            public_id=f"videonum{course.id}"
        )
        video_url = video_upload_result.get("secure_url")

        video_material = CourseMaterial(
            course_id=course.id,
            file_name=course_video.filename,
            file_path=video_url,
            file_type=course_video.content_type,
            file_category="record"
        )
        db.add(video_material)
        materials.append(video_material)

    db.commit()

    # 5. Utiliser les infos de l'utilisateur connecté (instructeur)
    instructor_dict = {
        "id": current_user.id,
        "name": current_user.nom,
        "prenom": current_user.prenom,
        "email": current_user.email,
        "departement": current_user.departement
    }

    # 6. Préparer la réponse complète
    # Cherche l'URL de l'image (catégorie photo)
    image_url = None
    for m in materials:
        if m.file_category == "photo":
            image_url = m.file_path
            break

    response = {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "departement": course.departement,
        "external_links": course.external_links,
        "quiz_link": course.quiz_link,
        "instructor_id": course.instructor_id,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
        "instructor": instructor_dict,
        "image_url": image_url,
        "materials": [
            {
                "id": m.id,
                "course_id": m.course_id,
                "file_name": m.file_name,
                "file_type": m.file_type,
                "file_category": m.file_category,
                "file_path": ("/pdfs/" + m.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if m.file_type == "application/pdf" and m.file_path.startswith("uploads/pdfs") else m.file_path,
                "uploaded_at": m.uploaded_at
            }
            for m in materials
        ]
    }

    # Send notifications
    notify_new_course(db, course)  # Notify admin
    notify_professor_new_course(db, course)  # Notify professors in same department
    notify_employer_new_course(db, course)  # Notify employers in same department

    return response


@app.get("/courses/", response_model=List[CourseSchema])
def get_courses(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    # Base query
    query = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor),
        sqlalchemy.orm.joinedload(Course.materials)
    )
    
    # Si l'utilisateur est un employer, filtrer par département
    if current_user.role == "employer":
        query = query.filter(Course.departement == current_user.departement)
    
    # Appliquer la pagination
    courses = query.offset(skip).limit(limit).all()
    
    # Préparer la réponse avec les informations supplémentaires
    course_list = []
    for course in courses:
        # Trouver l'image du cours
        course_image = next(
            (material for material in course.materials if material.file_category == 'photo'),
            None
        )
        
        # Convert instructor to dictionary
        instructor_dict = {
            "id": course.instructor.id,
            "nom": course.instructor.nom,
            "prenom": course.instructor.prenom,
            "email": course.instructor.email,
            "departement": course.instructor.departement
        } if course.instructor else None
        
        # Créer le dictionnaire de cours avec les informations supplémentaires
        course_dict = {
            "id": course.id,
            "title": course.title,
            "description": course.description or "",
            "departement": course.departement,
            "external_links": course.external_links or "",
            "quiz_link": course.quiz_link or "",
            "instructor_id": course.instructor_id,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "instructor": instructor_dict,
            "materials": [
                {
                    "id": material.id,
                    "course_id": material.course_id,
                    "file_name": material.file_name,
                    "file_type": material.file_type,
                    "file_category": material.file_category or "material",
                    "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
                    "uploaded_at": material.uploaded_at
                }
                for material in course.materials
            ],
            "image_url": course_image.file_path if course_image else None
        }
        course_list.append(course_dict)
    
    return course_list

@app.get("/courses/by-department", response_model=List[CourseSchema])
def get_courses_by_department(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retourne les cours du département de l'utilisateur connecté.
    """
    if not current_user.departement:
        raise HTTPException(status_code=400, detail="Département non défini pour cet utilisateur.")
    courses = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor),
        sqlalchemy.orm.joinedload(Course.materials)
    ).filter(Course.departement == current_user.departement).all()

    course_list = []
    for course in courses:
        course_image = next(
            (material for material in course.materials if material.file_category == 'photo'),
            None
        )
        
        # Convert instructor to dictionary
        instructor_dict = {
            "id": course.instructor.id,
            "nom": course.instructor.nom,
            "prenom": course.instructor.prenom,
            "email": course.instructor.email,
            "departement": course.instructor.departement
        } if course.instructor else None
        
        course_dict = {
            "id": course.id,
            "title": course.title,
            "description": course.description or "",
            "departement": course.departement,
            "external_links": course.external_links or "",
            "quiz_link": course.quiz_link or "",
            "instructor_id": course.instructor_id,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "instructor": instructor_dict,
            "materials": [
                {
                    "id": material.id,
                    "course_id": material.course_id,
                    "file_name": material.file_name,
                    "file_type": material.file_type,
                    "file_category": material.file_category or "material",
                    "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
                    "uploaded_at": material.uploaded_at
                }
                for material in course.materials
            ],
            "image_url": course_image.file_path if course_image else None
        }
        course_list.append(course_dict)

    return course_list

@app.get("/courses/{course_id}", response_model=CourseSchema)
def get_course(
    course_id: int,
    db: Session = Depends(get_db)
):
    course = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor),
        sqlalchemy.orm.joinedload(Course.materials)
    ).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Trouver l'image du cours
    course_image = next(
        (material for material in course.materials if material.file_category == 'photo'),
        None
    )
    
    # Préparer le dictionnaire d'instructeur
    instructor_dict = {
        "id": course.instructor.id,
        "nom": course.instructor.nom,
        "prenom": course.instructor.prenom,
        "email": course.instructor.email,
        "departement": course.instructor.departement
    } if course.instructor else None
    
    # Créer la réponse complète
    response = {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "departement": course.departement,
        "external_links": course.external_links or "",
        "quiz_link": course.quiz_link or "",
        "instructor_id": course.instructor_id,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
        "instructor": instructor_dict,
        "materials": [
            {
                "id": material.id,
                "course_id": material.course_id,
                "file_name": material.file_name,
                "file_type": material.file_type,
                "file_category": material.file_category or "material",
                "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
                "uploaded_at": material.uploaded_at
            }
            for material in course.materials
        ],
         "image_url": course_image.file_path if course_image else None
    }
    
    return response

@app.get("/courses/{course_id}/materials/", response_model=List[CourseMaterialSchema])
def get_course_materials(
    course_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Vérifier que le cours existe
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Récupérer les matériaux
    materials = course.materials
    
    # Préparer la réponse
    result = [
        {
            "id": material.id,
            "course_id": material.course_id,
            "file_name": material.file_name,
            "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
            "file_type": material.file_type,
            "file_category": material.file_category or "material",
            "uploaded_at": material.uploaded_at
        }
        for material in materials
    ]
    
    return result

@app.post("/courses/{course_id}/enroll")
async def enroll_in_course(
    course_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Vérifier que le cours existe
    course = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor)
    ).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Vérifier si déjà inscrit
    existing_progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    
    if existing_progress:
        raise HTTPException(status_code=400, detail="Already enrolled in this course")
    
    # Créer un nouvel enregistrement de progression avec la date d'inscription
    progress = CourseProgress(
        user_id=current_user.id,
        course_id=course_id,
        start_date=datetime.utcnow(),
        status="En cours",
        progress=0,
        is_completed=False,
        last_accessed=datetime.utcnow()
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)

    # Créer une notification
    create_notification(
        db=db,
        user_id=current_user.id,
        title="Inscription à un cours",
        message=f"Vous êtes maintenant inscrit au cours {course.title}",
        type="course_enrollment",
        course_id=course.id
    )

    # Préparer la réponse
    return {
        "success": True,
        "message": f"Inscrit au cours {course.title}",
        "course": {
            "id": course.id,
            "title": course.title,
            "instructor": f"{course.instructor.nom} {course.instructor.prenom}" if course.instructor else "Unknown",
            "departement": course.departement,
            "start_date": progress.start_date,
            "status": progress.status,
            "progress": f"{progress.progress:.1f}%"
        }
    }

@app.put("/courses/{course_id}/complete")
async def mark_course_as_completed(
    course_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Vérifier que le cours existe
    course = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor)
    ).filter(Course.id == course_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Récupérer la progression
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")
    
    # Marquer le cours comme terminé
    progress.is_completed = True
    progress.status = "Terminé"
    progress.completion_date = datetime.utcnow()
    progress.progress = 100
    progress.last_accessed = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    
    # Create a notification using the notification service
    create_notification(
        db=db,
        user_id=current_user.id,
        title="Cours terminé",
        message=f"Félicitations ! Vous avez terminé le cours {course.title}",
        type="course_completion",
        course_id=course.id
    )
    
    return {
        "success": True,
        "message": "Cours marqué comme terminé",
        "course": {
            "id": course.id,
            "title": course.title,
            "instructor": f"{course.instructor.nom} {course.instructor.prenom}" if course.instructor else "Unknown"
        },
        "completion_details": {
            "completion_date": progress.completion_date.strftime("%d/%m/%Y"),
            "total_duration": f"{(progress.completion_date - progress.start_date).days} jours",
            "progress": "100%",
            "status": progress.status
        }
    }

@app.get("/courses/{course_id}/progress")
async def get_course_progress(
    course_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Récupérer le cours et vérifier son existence
    course = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor)
    ).filter(Course.id == course_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Récupérer la progression
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")
    
    # Mettre à jour le dernier accès
    progress.last_accessed = datetime.utcnow()
    db.commit()
    
    # Préparer la réponse
    return {
        "success": True,
        "course_id": course.id,
        "course_title": course.title,
        "instructor": {
            "id": course.instructor.id,
            "name": f"{course.instructor.nom} {course.instructor.prenom}"
        } if course.instructor else None,
        "progress_details": {
            "enrollment_date": progress.start_date.strftime("%d/%m/%Y"),
            "last_accessed": progress.last_accessed.strftime("%d/%m/%Y %H:%M"),
            "completion_date": progress.completion_date.strftime("%d/%m/%Y") if progress.completion_date else None,
            "progress_value": progress.progress,
            "progress_percent": f"{progress.progress:.1f}%",
            "status": progress.status,
            "is_completed": progress.is_completed,
            "duration": f"{(datetime.utcnow() - progress.start_date).days} jours"
        }
    }

@app.put("/courses/{course_id}/progress")
async def update_course_progress(
    course_id: int,
    progress_value: float,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Get progress record
    progress = db.query(CourseProgress).filter(
        CourseProgress.user_id == current_user.id,
        CourseProgress.course_id == course_id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")
    
    # Update progress
    progress.progress = min(100, max(0, progress_value))  # Ensure progress is between 0 and 100
    progress.last_accessed = datetime.utcnow()
    
    # Automatically mark as completed if progress reaches 100%
    if progress.progress >= 100 and not progress.is_completed:
        progress.is_completed = True
        progress.status = "Terminé"
        progress.completion_date = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    
    # Notify student about progress update
    notify_course_progress(db, current_user.id, progress.course, progress.progress)
    
    return {
        "course_title": progress.course.title,
        "current_progress": f"{progress.progress:.1f}%",
        "status": progress.status,
        "last_updated": progress.last_accessed.strftime("%d/%m/%Y %H:%M")
    }

# Dashboard routes
@app.get("/dashboard/admin")
async def admin_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
   
    
    # Get courses where current user is the instructor
    courses = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor),
        sqlalchemy.orm.joinedload(Course.materials)
    ).filter(Course.instructor_id == current_user.id).all()
    
    # Prepare response with the same structure as get_courses
    course_list = []
    for course in courses:
        # Find course image
        course_image = next(
            (material for material in course.materials if material.file_category == 'photo'),
            None
        )
        
        # Convert instructor to dictionary
        instructor_dict = {
            "id": course.instructor.id,
            "nom": course.instructor.nom,
            "prenom": course.instructor.prenom,
            "email": course.instructor.email,
            "departement": course.instructor.departement
        } if course.instructor else None
        
        # Create course dictionary with additional information
        course_dict = {
            "id": course.id,
            "title": course.title,
            "description": course.description or "",
            "departement": course.departement,
            "external_links": course.external_links or "",
            "quiz_link": course.quiz_link or "",
            "instructor_id": course.instructor_id,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "instructor": instructor_dict,
            "materials": [
                {
                    "id": material.id,
                    "course_id": material.course_id,
                    "file_name": material.file_name,
                    "file_type": material.file_type,
                    "file_category": material.file_category or "material",
                    "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
                    "uploaded_at": material.uploaded_at
                }
                for material in course.materials
            ],
            "image_url": course_image.file_path if course_image else None
        }
        course_list.append(course_dict)
    
    return course_list

@app.get("/dashboard/prof")
async def prof_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if current_user.role != "prof":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. professor role required."
        )
    
    # Get professor's courses with joined instructor and materials
    courses = db.query(Course).options(
        sqlalchemy.orm.joinedload(Course.instructor),
        sqlalchemy.orm.joinedload(Course.materials)
    ).filter(Course.instructor_id == current_user.id).all()
    
    # Prepare response with the same structure as get_courses
    course_list = []
    for course in courses:
        # Find course image
        course_image = next(
            (material for material in course.materials if material.file_category == 'photo'),
            None
        )
        
        # Convert instructor to dictionary
        instructor_dict = {
            "id": course.instructor.id,
            "nom": course.instructor.nom,
            "prenom": course.instructor.prenom,
            "email": course.instructor.email,
            "departement": course.instructor.departement
        } if course.instructor else None
        
        # Create course dictionary with additional information
        course_dict = {
            "id": course.id,
            "title": course.title,
            "description": course.description or "",
            "departement": course.departement,
            "external_links": course.external_links or "",
            "quiz_link": course.quiz_link or "",
            "instructor_id": course.instructor_id,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "instructor": instructor_dict,
            "materials": [
                {
                    "id": material.id,
                    "course_id": material.course_id,
                    "file_name": material.file_name,
                    "file_type": material.file_type,
                    "file_category": material.file_category or "material",
                    "file_path": ("/pdfs/" + material.file_name.replace(" ", "_").replace("\\", "/").replace("/", "/")) if material.file_type == "application/pdf" and material.file_path.startswith("uploads/pdfs") else material.file_path,
                    "uploaded_at": material.uploaded_at
                }
                for material in course.materials
            ],
            "image_url": course_image.file_path if course_image else None
        }
        course_list.append(course_dict)
    
    return course_list

@app.get("/dashboard/employer")
async def employer_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if current_user.role != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. employer role required."
        )
    
    # Get all available courses
    courses = db.query(Course).all()
    
    return {
        "available_courses": [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "instructor": {
                    "nom": course.instructor.nom,
                },
                "materials_count": len(course.materials)
            }
            for course in courses
        ]
    }

@app.put("/courses/{course_id}", response_model=CourseSchema)
def update_course(
    course_id: int,
    course_update: CourseBase,
    current_user: Annotated[User, Depends(verify_professor_or_admin)],
    db: Session = Depends(get_db)
):
    # Get existing course
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Verify that the current user is the course instructor
    if db_course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own courses"
        )
    
    # Update course details
    for field, value in course_update.dict(exclude_unset=True).items():
        setattr(db_course, field, value)
    
    db_course.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_course)
    return db_course

@app.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    current_user: Annotated[User, Depends(verify_professor_or_admin)],
    db: Session = Depends(get_db)
):
    # Get existing course
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Verify that the current user is the course instructor
    if course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own courses"
        )
    
    # Notify admin about course deletion
    notify_course_deleted(db, course)
    
    # Delete the course
    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}

@app.delete("/courses/{course_id}/materials/{material_id}")
def delete_course_material(
    course_id: int,
    material_id: int,
    current_user: Annotated[User, Depends(verify_professor_or_admin)],
    db: Session = Depends(get_db)
):
    # Get the material and verify it belongs to the specified course
    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id
    ).first()
    
    if material is None:
        raise HTTPException(status_code=404, detail="Course material not found")
    
    # Verify that the current user is the course instructor
    if material.course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete materials from your own courses"
        )
    
    # Delete the material
    db.delete(material)
    db.commit()
    return {"message": "Course material deleted successfully"}

@app.get("/notifications/", response_model=NotificationResponse)
def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get all notifications for the current user.
    Notifications are automatically marked as read when fetched.
    Returns both notifications and unread count.
    """
    try:
        return get_user_notifications(db, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching notifications: {str(e)}"
        )

@app.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Mark a specific notification as read"""
    try:
        notification = mark_notification_as_read(db, notification_id, current_user.id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or you don't have permission to access it"
            )
        return {
            "message": "Notification marked as read",
            "notification": {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "type": notification.type,
                "is_read": notification.is_read,
                "created_at": notification.created_at
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking notification as read: {str(e)}"
        )

@app.post("/messages/", response_model=MessageInDB)
async def send_message(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    content: str = Form(...),
    receiver_id: int = Form(...),
    file: Optional[UploadFile] = File(None)
):
    # Verify receiver exists
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    return create_message(
        db=db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        file=file
    )

@app.get("/messages/", response_model=List[MessageInDB])
def get_messages(
    current_user: Annotated[User, Depends(get_current_user)],
    message_type: str = "received",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    if message_type not in ["received", "sent"]:
        raise HTTPException(status_code=400, detail="Invalid message type")
    
    return get_user_messages(
        db=db,
        user_id=current_user.id,
        message_type=message_type,
        skip=skip,
        limit=limit
    )

@app.get("/messages/{message_id}", response_model=MessageInDB)
def read_message(
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    message = get_message(db, message_id, current_user.id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@app.put("/messages/{message_id}/read")
def mark_message_read(
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    message = mark_message_as_read(db, message_id, current_user.id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message marked as read"}

@app.delete("/messages/{message_id}")
def remove_message(
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if not delete_message(db, message_id, current_user.id):
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message deleted successfully"}

@app.get("/messages/file/{message_id}")
async def get_message_file(
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    message = get_message(db, message_id, current_user.id)
    if not message or not message.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.exists(message.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        message.file_path,
        media_type=message.file_type,
        filename=os.path.basename(message.file_path)
    )

@app.get("/public/users", response_model=List[UserSchema])
def get_all_users(db: Session = Depends(get_db)):
    """
    Public endpoint to fetch all users.
    """
    users = db.query(User).all()
    return users

@app.post("/request", response_model=ConferenceRequestOut)
async def request_conference(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    type: str = Form(...),
    departement: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["prof", "admin"]:
        raise HTTPException(status_code=403, detail="Only prof or admin can request conferences")

    # Convert date string to datetime
    try:
        conference_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Please use YYYY-MM-DD"
        )

    # Validate time format
    try:
        datetime.strptime(time, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format. Please use HH:MM"
        )

    # Create conference data
    conference_data = {
        "name": name,
        "description": description,
        "link": link,
        "type": type,
        "departement": departement,
        "date": conference_date,
        "time": time,
        "requested_by_id": current_user.id,
        # Set status to approved if user is admin
        "status": ConferenceStatus.approved if current_user.role == "admin" else ConferenceStatus.pending
    }

    # Create new conference request
    new_conf = ConferenceRequest(**conference_data)
    db.add(new_conf)
    db.commit()
    db.refresh(new_conf)
    
    # Notify admin about new conference request
    notify_conference_request(db, current_user, name)

    return new_conf

@app.put("/admin/approve/{conf_id}", response_model=ConferenceRequestOut)
def approve_conference(
    conf_id: int,
    approve: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can approve or deny conferences")

    conf = db.query(ConferenceRequest).filter(ConferenceRequest.id == conf_id).first()
    if not conf:
        raise HTTPException(status_code=404, detail="Conference not found")

    conf.status = ConferenceStatus.approved if approve else ConferenceStatus.denied
    db.commit()
    db.refresh(conf)

    # Notify professor about conference status
    notify_conference_status(db, conf.requested_by, conf.name, approve)

    return conf

@app.get("/admin/pending-conferences", response_model=List[ConferenceRequestOut])
def get_pending_conference_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can view pending conference requests"
        )
    
    pending_requests = db.query(ConferenceRequest).options(
        sqlalchemy.orm.joinedload(ConferenceRequest.requested_by)
    ).filter(
        ConferenceRequest.status == ConferenceStatus.pending
    ).order_by(ConferenceRequest.date).all()
    
    return pending_requests

@app.get("/prof/my-conferences", response_model=List[ConferenceRequestOut])
def get_professor_conferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if current_user.role != "prof":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only professors can view their conference requests"
        )
    
    professor_requests = db.query(ConferenceRequest).options(
        sqlalchemy.orm.joinedload(ConferenceRequest.requested_by)
    ).filter(
        ConferenceRequest.requested_by_id == current_user.id
    ).order_by(ConferenceRequest.date.desc()).all()
    
    return professor_requests

@app.get("/calendar", response_model=List[ConferenceRequestOut])
def get_calendar(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Base query for conferences with joined user data
    query = db.query(ConferenceRequest).options(
        sqlalchemy.orm.joinedload(ConferenceRequest.requested_by)
    )
    
    # Filter based on user role
    if current_user.role == "employer":
        # For employers, only show conferences from their department
        query = query.filter(ConferenceRequest.departement == current_user.departement)
    elif current_user.role == "prof":
        # For professors, show all conferences
        pass
    elif current_user.role == "admin":
        # For admins, show all conferences
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid role."
        )
    
    # Get only approved conferences
    query = query.filter(ConferenceRequest.status == ConferenceStatus.approved)
    
    # Order by date
    query = query.order_by(ConferenceRequest.date)
    
    # Execute query
    conferences = query.all()
    
    return conferences

@app.get("/conferences/{conference_id}", response_model=ConferenceRequestOut)
def get_conference(
    conference_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    conference = db.query(ConferenceRequest).options(
        sqlalchemy.orm.joinedload(ConferenceRequest.requested_by)
    ).filter(ConferenceRequest.id == conference_id).first()
    
    if not conference:
        raise HTTPException(status_code=404, detail="Conference not found")
    
    # Check if user has access to this conference
    if current_user.role == "employer" and conference.departement != current_user.departement:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conference"
        )
    
    return conference

@app.get("/personal-info", response_model=UserPersonalInfo)
def get_personal_info(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get user's personal information"""
    return {
        "telephone": current_user.telephone
    }

@app.put("/personal-info")
def update_personal_info(
    info: UserPersonalInfoUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Update user's personal information"""
    if info.telephone is not None:
        current_user.telephone = info.telephone
    
    db.commit()
    return {"message": "Personal information updated successfully"}

@app.get("/preferences", response_model=UserPreferences)
def get_user_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get user's preferences (language and theme)"""
    return {
        "language": current_user.language,
        "theme": current_user.theme
    }

@app.put("/preferences")
def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Update user's preferences (language and theme)"""
    if preferences.language is not None:
        if preferences.language not in ["fr", "en"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid language. Must be 'fr' or 'en'"
            )
        current_user.language = preferences.language
    
    if preferences.theme is not None:
        if preferences.theme not in ["light", "dark"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid theme. Must be 'light' or 'dark'"
            )
        current_user.theme = preferences.theme
    
    db.commit()
    return {"message": "Preferences updated successfully"}

@app.put("/password")
def update_password(
    password_update: PasswordUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Update user's password"""
    # Verify current password
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Verify new passwords match
    if password_update.new_password != password_update.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_update.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@app.put("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    user_update: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Admin endpoint to update another user's information"""
    # Verify admin role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can update user information"
        )
    
    # Get the user to update
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user information
    if user_update.nom is not None:
        user.nom = user_update.nom
    if user_update.prenom is not None:
        user.prenom = user_update.prenom
    if user_update.departement is not None:
        user.departement = user_update.departement
    if user_update.role is not None:
        # Validate role
        if user_update.role not in ["prof", "employer"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be 'prof' or 'employer'"
            )
        user.role = user_update.role
    
    try:
        db.commit()
        db.refresh(user)
        return {
            "message": "User information updated successfully",
            "updated_user": {
                "id": user.id,
                "nom": user.nom,
                "prenom": user.prenom,
                "departement": user.departement,
                "role": user.role
            }
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while updating user"
        )

@app.delete("/conferences/{conference_name}")
def delete_conference(
    conference_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Delete a conference request"""
    # Vérifier que l'utilisateur est le propriétaire de la conférence ou un admin
    conference = db.query(ConferenceRequest).filter(
        ConferenceRequest.name == conference_name,
        ConferenceRequest.requested_by_id == current_user.id
    ).first()

    if not conference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande de formation non trouvée ou vous n'avez pas le droit de la supprimer"
        )

    # Supprimer la conférence
    db.delete(conference)
    db.commit()

    return {"message": "Demande de formation supprimée avec succès"}

