from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Engineering Drawing Intelligence PoC"
    api_prefix: str = "/api/v1"
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    storage_dir: Path = Path("data/output/drawings")
    storage_backend: Literal["local", "gcs"] = "local"
    gcs_bucket: str | None = None
    ocr_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OCR_ENABLED", "DRAWING_OCR_ENABLED"),
    )
    ocr_provider: str = Field(
        default="tesseract",
        validation_alias=AliasChoices("OCR_PROVIDER", "DRAWING_OCR_PROVIDER"),
    )
    level3_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("LEVEL3_ENABLED", "DRAWING_LEVEL3_ENABLED"),
    )
    level4_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("LEVEL4_ENABLED", "DRAWING_LEVEL4_ENABLED"),
    )
    demo_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEMO_MODE", "DRAWING_DEMO_MODE"),
    )
    vision_dpi: int = Field(default=200, ge=72, le=600)
    vision_debug_overlays: bool = False
    native_text_min_characters: int = Field(default=20, ge=1)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_prefix="DRAWING_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        if self.storage_backend == "gcs":
            if not self.gcs_bucket or not self.gcs_bucket.strip():
                raise ValueError("DRAWING_GCS_BUCKET is required when DRAWING_STORAGE_BACKEND=gcs")
            # Accept a bucket name, never a URL or an object prefix.
            if self.gcs_bucket != self.gcs_bucket.strip() or any(
                character in self.gcs_bucket for character in "/\\:"
            ):
                raise ValueError(
                    "DRAWING_GCS_BUCKET must be a bucket name without a path or scheme"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
