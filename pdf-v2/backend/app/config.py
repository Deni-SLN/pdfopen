from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./sofia.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-this-to-a-long-random-string-min-32-chars"
    JWT_EXPIRE_MINUTES: int = 1440
    MAX_FILE_SIZE_MB: int = 100
    RETENTION_HOURS: int = 1
    WORKER_CONCURRENCY: int = 2
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    STORAGE_ROOT: str = "./storage"
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
