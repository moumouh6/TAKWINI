from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Admin
    default_admin_email: str = "admin@gig.dz"
    default_admin_password: str = "admin123"

    # Cloudinary (temporary — removed in Step 5)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Local uploads
    upload_dir: str = "uploads"

    class Config:
        env_file = ".env"

settings = Settings()