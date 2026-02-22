"""
Integration tests for Qdrant client operations.

IMPORTANT: These tests require a running Qdrant instance.
Start with: docker compose up -d
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from codeguard.qdrant_store import QdrantManager


@pytest.fixture(scope="module")
def qdrant():
    """Qdrant manager connected to local instance."""
    manager = QdrantManager(host="localhost", port=6333)
    return manager


@pytest.fixture(scope="module")
def test_collection(qdrant):
    """Create a temporary test collection, clean up after."""
    collection_name = "_test_codeguard"
    # Ensure clean state
    try:
        qdrant.client.delete_collection(collection_name)
    except Exception:
        pass

    qdrant.client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "size": 768,
            "distance": "Cosine",
        },
    )
    yield collection_name

    # Cleanup
    try:
        qdrant.client.delete_collection(collection_name)
    except Exception:
        pass


class TestQdrantManager:
    """Integration tests for QdrantManager."""

    def test_init_collections(self, qdrant):
        """Test that all 5 collections can be created."""
        results = qdrant.init_collections()
        assert len(results) == 5
        assert all(v in ("created", "exists") for v in results.values())
        # Verify all expected collections
        for name in ["tickets", "standards", "adr", "history", "codebase"]:
            assert name in results

    def test_upsert_and_search(self, qdrant, test_collection):
        """Test basic upsert and semantic search."""
        # Create some fake vectors (768-dim)
        import random
        random.seed(42)

        texts = ["error handling best practices", "SQL injection prevention"]
        vectors = [[random.random() for _ in range(768)] for _ in range(2)]
        metadata = [
            {"type": "standard", "category": "error_handling"},
            {"type": "standard", "category": "security"},
        ]

        count = qdrant.upsert_points(test_collection, texts, vectors, metadata)
        assert count == 2

        # Search with one of the vectors
        results = qdrant.search(test_collection, vectors[0], top_k=2)
        assert len(results) >= 1
        assert results[0]["text"] in texts

    def test_search_with_filter(self, qdrant, test_collection):
        """Test filtered search."""
        import random
        random.seed(99)

        vector = [random.random() for _ in range(768)]
        results = qdrant.search(
            test_collection,
            vector,
            top_k=5,
            filter_conditions={"category": "security"},
        )
        for r in results:
            assert r["metadata"]["category"] == "security"

    def test_exact_match(self, qdrant, test_collection):
        """Test exact metadata match retrieval."""
        results = qdrant.exact_match(
            test_collection, field="category", value="error_handling"
        )
        assert len(results) >= 1
        assert results[0]["metadata"]["category"] == "error_handling"

    def test_collection_count(self, qdrant, test_collection):
        """Test point counting."""
        count = qdrant.collection_count(test_collection)
        assert count >= 2

    def test_upsert_empty_list(self, qdrant, test_collection):
        """Upserting empty data should be a no-op."""
        count = qdrant.upsert_points(test_collection, [], [], [])
        assert count == 0
