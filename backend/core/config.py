from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH Disaster Structural Platform"
    DATABASE_URL: str = "postgresql://sih_user:sih_password@db:5432/disaster_db"
    REDIS_URL: str = "redis://redis:6379/0"
    TWITTER_BEARER_TOKEN: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
