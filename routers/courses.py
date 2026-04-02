from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
import os, shutil, re
from dependencies import get_db, get_current_user, require_prof_or_admin
from models.user import User
from models.course import Course, CourseMaterial, CourseProgress
from services.notification_service import (
    notify_new_course, notify_professor_new_course,
    notify_employer_new_course, notify_course_deleted, notify_material_added
)

router = APIRouter(tags=["Courses"])

def clean_filename(filename):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', filename)

def save_local_file(file: UploadFile, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    filename = clean_filename(file.filename)
    file_path = os.path.join(folder, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path

# ─── Get All Courses ──────────────────────────────────────────
@router.get("/courses/")
def get_courses(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Course).options(joinedload(Course.materials))
    if current_user.role == "employer":
        query = query.filter(Course.departement == current_user.departement)
    return query.offset(skip).limit(min(limit, 100)).all()

# ─── Get Courses By Department ────────────────────────────────
@router.get("/courses/by-department")
def get_courses_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Course).filter(
        Course.departement == current_user.departement
    ).options(joinedload(Course.materials)).all()

# ─── Get Single Course ────────────────────────────────────────
@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    course = db.query(Course).options(
        joinedload(Course.materials),
        joinedload(Course.instructor)
    ).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

# ─── Get Course Materials ─────────────────────────────────────
@router.get("/courses/{course_id}/materials/")
def get_course_materials(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return db.query(CourseMaterial).filter(
        CourseMaterial.course_id == course_id
    ).all()

# ─── Create Course ────────────────────────────────────────────
@router.post("/courses/")
def create_course(
    title: str = Form(...),
    description: str = Form(...),
    departement: str = Form(...),
    external_links: Optional[str] = Form(None),
    quiz_link: Optional[str] = Form(None),
    course_image: UploadFile = File(...),
    course_pdf: UploadFile = File(...),
    course_video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_prof_or_admin)
):
    # 1. Create course
    course = Course(
        title=title,
        description=description,
        instructor_id=current_user.id,
        departement=departement,
        external_links=external_links,
        quiz_link=quiz_link,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    # 2. Save image locally
    image_path = save_local_file(
        course_image, f"uploads/courses/{course.id}/images"
    )
    db.add(CourseMaterial(
        course_id=course.id,
        file_name=clean_filename(course_image.filename),
        file_path=image_path,
        file_type=course_image.content_type,
        file_category="photo"
    ))

    # 3. Save PDF locally
    pdf_path = save_local_file(
        course_pdf, f"uploads/courses/{course.id}/pdfs"
    )
    db.add(CourseMaterial(
        course_id=course.id,
        file_name=clean_filename(course_pdf.filename),
        file_path=pdf_path,
        file_type="application/pdf",
        file_category="material"
    ))

    # 4. Save video if provided
    if course_video and course_video.filename:
        video_path = save_local_file(
            course_video, f"uploads/courses/{course.id}/videos"
        )
        db.add(CourseMaterial(
            course_id=course.id,
            file_name=clean_filename(course_video.filename),
            file_path=video_path,
            file_type=course_video.content_type,
            file_category="record"
        ))

    db.commit()
    db.refresh(course)

    # 5. Notify everyone
    notify_new_course(db, course)
    notify_professor_new_course(db, course)
    notify_employer_new_course(db, course)

    return course

# ─── Update Course ────────────────────────────────────────────
@router.put("/courses/{course_id}")
def update_course(
    course_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    external_links: Optional[str] = Form(None),
    quiz_link: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_prof_or_admin)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    if title: course.title = title
    if description: course.description = description
    if external_links: course.external_links = external_links
    if quiz_link: course.quiz_link = quiz_link
    course.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(course)
    return course

# ─── Delete Course ────────────────────────────────────────────
@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_prof_or_admin)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete local files
    course_folder = f"uploads/courses/{course_id}"
    if os.path.exists(course_folder):
        shutil.rmtree(course_folder)

    notify_course_deleted(db, course)
    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}

# ─── Delete Material ──────────────────────────────────────────
@router.delete("/courses/{course_id}/materials/{material_id}")
def delete_material(
    course_id: int,
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_prof_or_admin)
):
    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if os.path.exists(material.file_path):
        os.remove(material.file_path)
    db.delete(material)
    db.commit()
    return {"message": "Material deleted successfully"}