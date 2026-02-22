"""
FastEmbed wrapper for CodeGuard.

Uses snowflake-arctic-embed-m-v1.5 to produce 768-dimensional embeddings.
Singleton pattern to avoid reloading the model on every call.
"""

from typing import Optional

from fastembed import TextEmbedding
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import settings


class EmbeddingService:
    """Singleton wrapper around FastEmbed's TextEmbedding model."""

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[TextEmbedding] = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_model(self) -> TextEmbedding:
        """Lazily load the embedding model on first use."""
        if self._model is None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Loading embedding model..."),
            ) as progress:
                progress.add_task("loading", total=None)
                self._model = TextEmbedding(model_name=settings.embedding_model)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts and return a list of vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each is a list of floats, length 768).
        """
        if not texts:
            return []

        model = self._ensure_model()
        # FastEmbed returns a generator; materialise it
        embeddings = list(model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string and return its vector."""
        results = self.embed_texts([text])
        return results[0] if results else []


# Module-level convenience instance
embedding_service = EmbeddingService()
