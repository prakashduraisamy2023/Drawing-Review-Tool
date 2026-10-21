from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Engineering Drawing Intelligence PoC"
    api_prefix: str = "/api/v1"
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    storage_dir: Path = Path("data/output/drawings")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
