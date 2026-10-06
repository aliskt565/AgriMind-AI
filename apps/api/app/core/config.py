"""
Application configuration.

All configuration is read from environment variables (see .env.example at the
repo root). No secrets are hard-coded. This module is the single source of
truth for runtime configuration across the API.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    APP_NAME: str = "AgriMind AI API"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/agrimind_dev"

    # --- Auth / Security ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_this_is_a_dev_only_default_secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h, generous for a student project demo
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14 days

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- Object storage (abstraction; local-disk mock by default) ---
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_LOCAL_DIR: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 8

    # --- AI ---
    AI_MODE: str = "mock"  # mock | real  -- MUST default to mock; real requires explicit model wiring

    # --- AI Farm Copilot ---
    # Decoupled from AI_MODE so Copilot's provider can be swapped independently
    # of Crop Intelligence / Plant Vision (e.g. Copilot could go "real" on a
    # hosted LLM before a custom-trained vision model is ready, or vice versa).
    COPILOT_PROVIDER: str = "mock"  # mock | real
    # Placeholders only -- populate via a real .env file, never commit real values.
    # Left unset/empty in .env.example; a RealCopilotProvider implementation
    # would read these once COPILOT_PROVIDER=real is actually wired up.
    COPILOT_LLM_API_KEY: str = ""
    COPILOT_LLM_MODEL_NAME: str = ""

    # --- Weather ---
    WEATHER_PROVIDER: str = "mock"  # mock | real


@lru_cache
def get_settings() -> Settings:
    return Settings()
