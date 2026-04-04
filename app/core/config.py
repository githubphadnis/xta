import os
import secrets
from dotenv import load_dotenv

# 1. This line finds the local .env file and loads it into memory
load_dotenv()


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class Settings:
    PROJECT_NAME: str = "Xpense Tracking Application"
    PROJECT_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    
    # 2. Infrastructure Config (Loaded from .env with defaults)
    # The syntax is: os.getenv("VARIABLE_NAME", "default_value_if_missing")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "xta_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "xta_password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "xta_db")
    
    # 3. Security Config
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AUTH_REQUIRED: bool = _parse_bool(os.getenv("AUTH_REQUIRED"), True)
    BASE_CURRENCY: str = os.getenv("BASE_CURRENCY", "EUR").upper()
    FX_API_URL: str = os.getenv("FX_API_URL", "https://api.frankfurter.app")

    # 4. Construct the Database URL dynamically
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()