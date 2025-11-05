from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    environment: str = "development"
    api_prefix: str = "/api"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    openai_timeout_seconds: float = 120.0
    document_classification_use_llm: bool = True
    document_classification_max_prompt_chars: int = 4000
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    document_upload_max_files: int = 5
    document_upload_max_file_size_mb: int = 50
    document_retention_hours: int = 24  # ファイルの保持期限（時間）
    upload_storage_dir: str = "storage/uploads"
    metadata_storage_dir: str = "storage/metadata"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local", "../.env", "../.env.local", "../../.env", "../../../.env"),
        env_prefix="APP_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance so configuration loads once."""

    return Settings()


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_upload_storage_path(settings: Settings) -> Path:
    """Return an absolute path under which uploaded documents are stored."""

    return _resolve_path(settings.upload_storage_dir)


def resolve_metadata_storage_path(settings: Settings) -> Path:
    """Return an absolute path under which upload metadata is stored."""

    return _resolve_path(settings.metadata_storage_dir)
