"""
Unit tests for the embedding pipeline.

These tests require FastEmbed to download the model on first run (~400 MB).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from codeguard.embeddings import EmbeddingService


@pytest.fixture(scope="module")
def embed_service():
    """Shared embedding service instance for the test module."""
    return EmbeddingService()


class TestEmbeddingService:
    """Tests for the FastEmbed wrapper."""

    def test_embed_single_returns_vector(self, embed_service):
        vec = embed_service.embed_single("This is a test sentence.")
        assert isinstance(vec, list)
        assert len(vec) == 768  # snowflake-arctic-embed-m-v1.5 output dim
        assert all(isinstance(v, float) for v in vec)

    def test_embed_texts_batch(self, embed_service):
        texts = [
            "Error handling best practices",
            "SQL injection prevention",
            "Unit testing with pytest",
        ]
        result = embed_service.embed_texts(texts)
        assert len(result) == 3
        assert all(len(v) == 768 for v in result)

    def test_embed_empty_list(self, embed_service):
        result = embed_service.embed_texts([])
        assert result == []

    def test_different_texts_produce_different_vectors(self, embed_service):
        v1 = embed_service.embed_single("Python error handling")
        v2 = embed_service.embed_single("JavaScript async await")
        # Vectors should differ for semantically different texts
        assert v1 != v2

    def test_similar_texts_have_high_similarity(self, embed_service):
        v1 = embed_service.embed_single("error handling in Python")
        v2 = embed_service.embed_single("exception handling in Python")

        # Cosine similarity should be high for semantically close texts
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a ** 2 for a in v1) ** 0.5
        norm2 = sum(b ** 2 for b in v2) ** 0.5
        cosine_sim = dot_product / (norm1 * norm2)

        assert cosine_sim > 0.7, f"Expected high similarity, got {cosine_sim:.3f}"
