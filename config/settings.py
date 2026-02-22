"""
CodeGuard Configuration — loads settings from .env with sensible defaults.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels up from this file (config/settings.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All application settings, loaded from .env file at project root."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Plane (Ticket Source) ──
    plane_api_token: str = ""
    plane_base_url: str = "http://localhost:8080/api/v1"
    plane_workspace_slug: str = ""

    # ── GitHub ──
    github_token: str = ""
    github_org: str = ""
    github_repos: str = ""  # comma-separated list

    # ── Qdrant ──
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # ── Organisation ──
    org_name: str = "My Organisation"

    # ── Embedding Model ──
    embedding_model: str = "snowflake/snowflake-arctic-embed-m"
    embedding_dim: int = 768

    # ── Paths (relative to project root) ──
    standards_dir: str = "data/standards"
    adrs_dir: str = "data/adrs"
    authors_file: str = "data/authors.yaml"

    @property
    def github_repos_list(self) -> list[str]:
        """Parse comma-separated repo list into a Python list."""
        if not self.github_repos:
            return []
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def standards_path(self) -> Path:
        return PROJECT_ROOT / self.standards_dir

    @property
    def adrs_path(self) -> Path:
        return PROJECT_ROOT / self.adrs_dir

    @property
    def authors_path(self) -> Path:
        return PROJECT_ROOT / self.authors_file


# Singleton instance — import this everywhere
settings = Settings()
