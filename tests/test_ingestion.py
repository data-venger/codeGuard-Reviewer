"""
Integration tests for ingestion pipelines.

Tests the standards and ADR ingestion using the example data files.

IMPORTANT: Requires running Qdrant instance and initialised collections.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from codeguard.qdrant_store import qdrant_manager

# Project root for locating test data
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestStandardsIngestion:
    """Test standards Markdown ingestion with example data."""

    def test_ingest_example_standards(self):
        """Ingest example_python.md and verify chunks appear in Qdrant."""
        from codeguard.ingestion.standards import ingest_standards

        standards_dir = PROJECT_ROOT / "data" / "standards"
        count = ingest_standards(standards_dir=standards_dir)

        assert count > 0, "Expected at least one chunk from example standards"

        # Verify points exist in Qdrant
        collection_count = qdrant_manager.collection_count("standards")
        assert collection_count > 0


class TestADRIngestion:
    """Test ADR Markdown ingestion with example data."""

    def test_ingest_example_adrs(self):
        """Ingest example ADR and verify chunks appear in Qdrant."""
        from codeguard.ingestion.adrs import ingest_adrs

        adrs_dir = PROJECT_ROOT / "data" / "adrs"
        count = ingest_adrs(adrs_dir=adrs_dir)

        assert count > 0, "Expected at least one chunk from example ADR"

        collection_count = qdrant_manager.collection_count("adr")
        assert collection_count > 0


class TestAuthorLoading:
    """Test author profile loading from YAML."""

    def test_load_authors(self):
        """Load example authors.yaml and verify profiles."""
        from codeguard.ingestion.authors import AuthorRegistry

        registry = AuthorRegistry()
        count = registry.load(PROJECT_ROOT / "data" / "authors.yaml")

        assert count == 3

        # Check specific author
        alice = registry.get("alice-dev")
        assert alice is not None
        assert alice.level == "junior"
        assert alice.is_junior
        assert alice.team == "mobile-app"

        bob = registry.get("bob-engineer")
        assert bob is not None
        assert bob.is_senior

    def test_review_guidance_junior(self):
        """Junior authors should get detailed guidance."""
        from codeguard.ingestion.authors import AuthorRegistry

        registry = AuthorRegistry()
        registry.load(PROJECT_ROOT / "data" / "authors.yaml")

        guidance = registry.get_review_guidance("alice-dev")
        assert "detailed" in guidance.lower() or "learning" in guidance.lower()

    def test_review_guidance_senior(self):
        """Senior authors should get concise guidance."""
        from codeguard.ingestion.authors import AuthorRegistry

        registry = AuthorRegistry()
        registry.load(PROJECT_ROOT / "data" / "authors.yaml")

        guidance = registry.get_review_guidance("bob-engineer")
        assert "concise" in guidance.lower() or "edge case" in guidance.lower()

    def test_unknown_author(self):
        """Unknown authors should get default guidance."""
        from codeguard.ingestion.authors import AuthorRegistry

        registry = AuthorRegistry()
        registry.load(PROJECT_ROOT / "data" / "authors.yaml")

        profile = registry.get("unknown-person")
        assert profile is None

        guidance = registry.get_review_guidance("unknown-person")
        assert "unknown" in guidance.lower()
