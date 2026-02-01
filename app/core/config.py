import os
from dotenv import load_dotenv

# 1. This line finds the local .env file and loads it into memory
load_dotenv()

class Settings:
    PROJECT_NAME: str = "Xpense Tracking Application"
    PROJECT_VERSION: str = "0.1.0"
    
    # 2. Infrastructure Config (Loaded from .env with defaults)
    # The syntax is: os.getenv("VARIABLE_NAME", "default_value_if_missing")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "xta_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "xta_password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "xta_db")
    
    # 3. Security Config
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_default_key")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # 4. Construct the Database URL dynamically
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()