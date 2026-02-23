"""
Qdrant client wrapper for CodeGuard.

Handles connection, collection management, upsert, and search operations
across the five named collections: tickets, standards, adr, history, codebase.
"""

import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient, models
from rich.console import Console

from config.settings import settings

console = Console()

# Collection definitions with their metadata schemas
COLLECTIONS = {
    "tickets": "Plane issue descriptions, acceptance criteria, comments",
    "standards": "Coding rules chunked by category and language",
    "adr": "Architecture Decision Records per service",
    "history": "Past PR review comments and verdicts",
    "codebase": "Module summaries, service READMEs, dependency maps",
}


class QdrantManager:
    """Manages all Qdrant operations for CodeGuard."""

    def __init__(
        self,
        host: str = settings.qdrant_host,
        port: int = settings.qdrant_port,
        url: str = settings.qdrant_url,
        api_key: str = settings.qdrant_api_key,
    ):
        # Cloud mode: use URL + API key
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
            console.print(f"  [cyan]☁️  Qdrant Cloud: {url[:40]}...[/cyan]")
        else:
            # Local mode: use host + port
            self.client = QdrantClient(host=host, port=port)
        self.vector_size = settings.embedding_dim

    # ── Collection Management ──

    def init_collections(self) -> dict[str, str]:
        """
        Create all 5 collections if they don't already exist.

        Returns:
            dict mapping collection name → status ('created' or 'exists').
        """
        results = {}
        existing = {c.name for c in self.client.get_collections().collections}

        for name, description in COLLECTIONS.items():
            if name in existing:
                results[name] = "exists"
                console.print(f"  [dim]Collection '{name}' already exists[/dim]")
            else:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                results[name] = "created"
                console.print(f"  [green]✓ Created collection '{name}'[/green] — {description}")

        return results

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection entirely. Use with caution."""
        self.client.delete_collection(collection_name=collection_name)
        console.print(f"  [red]✗ Deleted collection '{collection_name}'[/red]")

    def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """Get point count and status for a collection."""
        info = self.client.get_collection(collection_name=collection_name)
        return {
            "name": collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value,
        }

    # ── Upsert Operations ──

    def upsert_points(
        self,
        collection_name: str,
        texts: list[str],
        vectors: list[list[float]],
        metadata_list: list[dict[str, Any]],
    ) -> int:
        """
        Batch upsert points into a collection.

        Args:
            collection_name: Target collection.
            texts: Original text chunks (stored in payload as 'text').
            vectors: Corresponding embedding vectors.
            metadata_list: List of metadata dicts, one per point.

        Returns:
            Number of points upserted.
        """
        if not texts:
            return 0

        assert len(texts) == len(vectors) == len(metadata_list), (
            f"Mismatched lengths: texts={len(texts)}, "
            f"vectors={len(vectors)}, metadata={len(metadata_list)}"
        )

        points = []
        for text, vector, metadata in zip(texts, vectors, metadata_list):
            point_id = str(uuid.uuid4())
            payload = {**metadata, "text": text}
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # Batch upsert in chunks of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch,
            )

        return len(points)

    # ── Search Operations ──

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search in a collection with optional metadata filtering.

        Args:
            collection_name: Collection to search.
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filter_conditions: Dict of {field: value} for must-match filters.

        Returns:
            List of dicts with keys: id, score, text, metadata.
        """
        qdrant_filter = None
        if filter_conditions:
            must_clauses = [
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
                for key, value in filter_conditions.items()
            ]
            qdrant_filter = models.Filter(must=must_clauses)

        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
        ).points

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "metadata": {
                    k: v for k, v in hit.payload.items() if k != "text"
                },
            }
            for hit in results
        ]

    def exact_match(
        self,
        collection_name: str,
        field: str,
        value: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retrieve points by exact metadata match (no vector query needed).

        Useful for fetching all chunks for a specific ticket by issue_key.

        Args:
            collection_name: Collection to search.
            field: Metadata field name.
            value: Exact value to match.
            top_k: Maximum results.

        Returns:
            List of dicts with keys: id, text, metadata.
        """
        results, _ = self.client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key=field,
                        match=models.MatchValue(value=value),
                    )
                ]
            ),
            limit=top_k,
        )

        return [
            {
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "metadata": {
                    k: v for k, v in point.payload.items() if k != "text"
                },
            }
            for point in results
        ]

    def collection_count(self, collection_name: str) -> int:
        """Return the number of points in a collection."""
        info = self.client.get_collection(collection_name=collection_name)
        return info.points_count or 0


# Module-level convenience instance
qdrant_manager = QdrantManager()
