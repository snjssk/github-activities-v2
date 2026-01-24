"""Configuration management."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings."""

    def __init__(self) -> None:
        self.github_token: str = os.getenv("GITHUB_TOKEN", "")
        self.github_org: str = os.getenv("GITHUB_ORG", "")
        self.target_users: list[str] = [
            u.strip()
            for u in os.getenv("TARGET_USERS", "").split(",")
            if u.strip()
        ]
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{Path(__file__).parent.parent.parent / 'data' / 'data.db'}",
        )

    def validate(self) -> None:
        """Validate required settings."""
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN is required")
        if not self.github_org:
            raise ValueError("GITHUB_ORG is required")


settings = Settings()
