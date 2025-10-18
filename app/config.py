"""Configuration management for Blog Pipeline."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # WordPress
    wp_base_url: str = Field(..., description="WordPress site URL")
    wp_user: str = Field(..., description="WordPress username")
    wp_app_password: str = Field(..., description="WordPress application password")

    # Slack
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")

    # Image generation (MVP: disabled)
    images_provider: str = Field("none", description="Image provider: none|openai|replicate")

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path("/opt/blog-pipeline"))
    inbox_dir: Path = Field(default_factory=lambda: Path("/opt/blog-pipeline/var/inbox"))
    work_dir: Path = Field(default_factory=lambda: Path("/opt/blog-pipeline/var/work"))
    published_dir: Path = Field(default_factory=lambda: Path("/opt/blog-pipeline/var/published"))

    # Queue settings
    db_path: Path = Field(default_factory=lambda: Path("/opt/blog-pipeline/var/queue.db"))
    max_retries: int = Field(5, description="Maximum retry attempts")
    retry_delays: list[int] = Field(
        default_factory=lambda: [60, 300, 900, 3600, 21600],  # 1m, 5m, 15m, 1h, 6h
        description="Retry delay in seconds"
    )

    # Server
    server_host: str = Field("0.0.0.0", description="FastAPI server host")
    server_port: int = Field(8000, description="FastAPI server port")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
