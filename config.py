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

    # Local uploads
    upload_dir: str = "uploads"

    # Redis
    redis_url: str = ""

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"

    class Config:
        env_file = ".env"

settings = Settings()