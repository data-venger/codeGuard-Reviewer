"""
Layer 6 — Author Context Metadata Loader.

Loads author profiles from a YAML file. This is a lookup table, not
an embedding collection — used at review time to adapt verbosity.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

from config.settings import settings

console = Console()


@dataclass
class AuthorProfile:
    """An author's profile for adaptive review verbosity."""

    github_handle: str
    level: str  # junior, mid, senior
    team: str
    modules: list[str]  # Areas of expertise

    @property
    def is_junior(self) -> bool:
        return self.level.lower() in ("junior", "intern", "new")

    @property
    def is_senior(self) -> bool:
        return self.level.lower() in ("senior", "staff", "principal", "lead")


class AuthorRegistry:
    """Registry of author profiles, loaded from YAML."""

    def __init__(self):
        self._profiles: dict[str, AuthorProfile] = {}
        self._loaded = False

    def load(self, authors_file: Path | None = None) -> int:
        """
        Load author profiles from YAML file.

        Args:
            authors_file: Path to authors.yaml (defaults to settings.authors_path).

        Returns:
            Number of profiles loaded.
        """
        target = authors_file or settings.authors_path

        if not target.exists():
            console.print(f"\n[yellow]⚠ Authors file not found: {target}[/yellow]")
            console.print("  [dim]Create data/authors.yaml to enable adaptive reviews.[/dim]")
            self._loaded = True
            return 0

        console.print(f"\n[bold]👤 Loading author profiles from {target.name}...[/bold]")

        with open(target, "r") as f:
            data = yaml.safe_load(f) or {}

        authors = data.get("authors", data) if isinstance(data, dict) else data

        if isinstance(authors, list):
            for entry in authors:
                profile = AuthorProfile(
                    github_handle=entry.get("github_handle", ""),
                    level=entry.get("level", "mid"),
                    team=entry.get("team", ""),
                    modules=entry.get("modules", []),
                )
                if profile.github_handle:
                    self._profiles[profile.github_handle.lower()] = profile

        self._loaded = True
        console.print(f"  [green]✓ Loaded {len(self._profiles)} author profiles[/green]")
        return len(self._profiles)

    def get(self, github_handle: str) -> Optional[AuthorProfile]:
        """
        Look up an author's profile.

        Returns None if the author is not in the registry.
        """
        if not self._loaded:
            self.load()
        return self._profiles.get(github_handle.lower())

    def get_review_guidance(self, github_handle: str) -> str:
        """
        Get review verbosity guidance for prompt injection.

        Returns a string to include in the review prompt that adapts
        the review style to the author's experience level.
        """
        profile = self.get(github_handle)
        if not profile:
            return "Reviewer note: Author experience level unknown. Use standard verbosity."

        if profile.is_junior:
            return (
                f"Reviewer note: Author '{github_handle}' is a {profile.level} developer "
                f"on the {profile.team} team. Provide detailed explanations, learning-oriented "
                f"suggestions, and include code examples. Be encouraging but thorough."
            )
        elif profile.is_senior:
            return (
                f"Reviewer note: Author '{github_handle}' is a {profile.level} developer "
                f"on the {profile.team} team with expertise in: {', '.join(profile.modules)}. "
                f"Be concise. Focus on edge cases, architectural concerns, and non-obvious issues. "
                f"Skip basic style/formatting feedback."
            )
        else:
            return (
                f"Reviewer note: Author '{github_handle}' is a {profile.level} developer "
                f"on the {profile.team} team. Use balanced verbosity."
            )

    @property
    def all_profiles(self) -> dict[str, AuthorProfile]:
        if not self._loaded:
            self.load()
        return dict(self._profiles)


# Module-level singleton
author_registry = AuthorRegistry()
