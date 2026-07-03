from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./bazys.db"
    secret_key: str = "change-me-in-production"
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
