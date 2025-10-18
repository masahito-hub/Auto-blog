"""Configuration management for Blog Pipeline."""

import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # WordPress (Required)
    wp_base_url: str = Field(..., description="WordPress site URL")
    wp_user: str = Field(..., description="WordPress username")
    wp_app_password: str = Field(..., description="WordPress application password")

    # Slack (Optional)
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")

    # Image generation (MVP: disabled)
    images_provider: str = Field("none", description="Image provider: none|openai|replicate")

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    inbox_dir: Optional[Path] = None
    work_dir: Optional[Path] = None
    published_dir: Optional[Path] = None
    db_path: Optional[Path] = None

    # Queue settings
    max_retries: int = Field(5, description="Maximum retry attempts")
    retry_delays: str = Field(
        "60,300,900,3600,21600",
        description="Comma-separated retry delays in seconds"
    )

    # Server
    server_host: str = Field("0.0.0.0", description="FastAPI server host")
    server_port: int = Field(8000, description="FastAPI server port")

    # Logging
    log_level: str = Field("INFO", description="Logging level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator("wp_base_url")
    @classmethod
    def validate_wp_url(cls, v: str) -> str:
        """Validate WordPress URL format."""
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("WordPress URL must start with http:// or https://")
        return v

    @field_validator("wp_app_password")
    @classmethod
    def validate_wp_password(cls, v: str) -> str:
        """Validate WordPress Application Password format."""
        # Remove spaces for storage, but validate format
        clean_password = v.replace(" ", "")
        if len(clean_password) != 24:
            raise ValueError(
                "WordPress Application Password should be 24 characters (6 groups of 4)"
            )
        return clean_password

    @field_validator("server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate server port range."""
        if not 1 <= v <= 65535:
            raise ValueError("Server port must be between 1 and 65535")
        return v

    def model_post_init(self, __context) -> None:
        """Initialize derived paths after model creation."""
        # Set default paths if not provided
        if self.inbox_dir is None:
            self.inbox_dir = self.base_dir / "var" / "inbox"
        if self.work_dir is None:
            self.work_dir = self.base_dir / "var" / "work"
        if self.published_dir is None:
            self.published_dir = self.base_dir / "var" / "published"
        if self.db_path is None:
            self.db_path = self.base_dir / "var" / "queue.db"

        # Create directories
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.published_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_retry_delays(self) -> list[int]:
        """Parse retry delays from comma-separated string."""
        return [int(d.strip()) for d in self.retry_delays.split(",")]

    def validate_environment(self) -> list[str]:
        """Validate that all required settings are properly configured."""
        errors = []

        # Check WordPress configuration
        if not self.wp_base_url:
            errors.append("WP_BASE_URL is required")
        if not self.wp_user:
            errors.append("WP_USER is required")
        if not self.wp_app_password:
            errors.append("WP_APP_PASSWORD is required")

        # Check paths are writable
        for path_name, path in [
            ("inbox_dir", self.inbox_dir),
            ("work_dir", self.work_dir),
            ("published_dir", self.published_dir),
        ]:
            if not os.access(path, os.W_OK):
                errors.append(f"{path_name} is not writable: {path}")

        return errors


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"Error loading configuration: {e}", file=sys.stderr)
    print("\nPlease ensure .env file exists and contains all required variables.", file=sys.stderr)
    print("See .env.example for reference.", file=sys.stderr)
    sys.exit(1)
