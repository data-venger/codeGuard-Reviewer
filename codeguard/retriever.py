"""
Multi-Namespace RAG Retriever for CodeGuard.

Queries all 5 Qdrant collections to assemble the full review context
for a given PR. This is the intelligence layer that makes the reviewer
org-aware rather than generic.
"""

import re
from dataclasses import dataclass, field

from rich.console import Console

from codeguard.embeddings import embedding_service
from codeguard.qdrant_store import qdrant_manager
from codeguard.ticket_extractor import extract_ticket_id

console = Console()


@dataclass
class ReviewContext:
    """All retrieved context for a PR review, structured by layer."""

    ticket_context: str = ""
    standards_context: str = ""
    adr_context: str = ""
    history_context: str = ""
    codebase_context: str = ""
    author_guidance: str = ""

    # Metadata
    ticket_id: str = ""
    matched_standards_count: int = 0
    matched_adr_count: int = 0
    matched_history_count: int = 0
    matched_codebase_count: int = 0

    @property
    def has_ticket(self) -> bool:
        return bool(self.ticket_context.strip())

    @property
    def total_context_tokens(self) -> int:
        """Approximate total tokens across all context."""
        all_text = (
            self.ticket_context
            + self.standards_context
            + self.adr_context
            + self.history_context
            + self.codebase_context
            + self.author_guidance
        )
        return len(all_text.split())


def _format_results(results: list[dict], max_chunks: int = 5) -> str:
    """Format Qdrant search results into a readable context string."""
    if not results:
        return "No relevant context found."

    parts = []
    for i, r in enumerate(results[:max_chunks], 1):
        score = r.get("score", 0)
        text = r.get("text", "")
        meta = r.get("metadata", {})

        header_parts = [f"[{i}]"]
        if "source_file" in meta:
            header_parts.append(f"Source: {meta['source_file']}")
        if "category" in meta:
            header_parts.append(f"Category: {meta['category']}")
        if score:
            header_parts.append(f"Relevance: {score:.2f}")

        header = " | ".join(header_parts)
        parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(parts)


def _detect_language_from_diff(diff_text: str) -> str:
    """Detect primary programming language from a diff."""
    extensions = re.findall(r"diff --git a/\S+\.(\w+)", diff_text)
    if not extensions:
        extensions = re.findall(r"\+\+\+ b/\S+\.(\w+)", diff_text)

    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "java": "java", "go": "go", "rs": "rust", "rb": "ruby",
        "sql": "sql", "jsx": "javascript", "tsx": "typescript",
    }

    counts: dict[str, int] = {}
    for ext in extensions:
        lang = lang_map.get(ext.lower(), ext.lower())
        counts[lang] = counts.get(lang, 0) + 1

    if counts:
        return max(counts, key=counts.get)
    return "general"


def _extract_changed_files(diff_text: str) -> list[str]:
    """Extract list of changed file paths from a diff."""
    files = re.findall(r"diff --git a/(\S+)", diff_text)
    return list(dict.fromkeys(files))  # Deduplicate, preserve order


def _extract_service_from_files(files: list[str]) -> str:
    """Infer service name from changed file paths."""
    if not files:
        return ""

    # Look for common service patterns: services/auth-service/..., apps/api/...
    for f in files:
        parts = f.split("/")
        if len(parts) >= 2:
            if parts[0] in ("services", "apps", "packages", "modules"):
                return parts[1]
    return ""


class Retriever:
    """Multi-namespace RAG retriever for PR review context."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def retrieve_ticket_context(self, issue_key: str) -> tuple[str, int]:
        """
        Retrieve ticket context by exact match on issue_key.

        Returns:
            (formatted_context, chunk_count)
        """
        if not issue_key:
            return "No ticket ID found in branch name or PR title.", 0

        try:
            results = qdrant_manager.exact_match(
                collection_name="tickets",
                field="issue_key",
                value=issue_key,
                top_k=5,
            )
            if results:
                texts = [r["text"] for r in results]
                return "\n\n".join(texts), len(results)
            else:
                return f"Ticket {issue_key} not found in the database. It may not have been ingested yet.", 0
        except Exception as e:
            return f"Error retrieving ticket: {e}", 0

    def retrieve_standards_context(
        self, diff_text: str, language: str = ""
    ) -> tuple[str, int]:
        """
        Semantic search for relevant coding standards based on diff content.

        Filters by detected language when available.
        """
        if not diff_text.strip():
            return "No diff provided.", 0

        try:
            # Embed a summary of the diff for semantic search
            # Use first ~500 tokens of diff to keep embedding focused
            search_text = " ".join(diff_text.split()[:500])
            query_vector = embedding_service.embed_single(search_text)

            filter_conditions = {}
            if language and language != "general":
                filter_conditions["language"] = language

            results = qdrant_manager.search(
                collection_name="standards",
                query_vector=query_vector,
                top_k=self.top_k,
                filter_conditions=filter_conditions if filter_conditions else None,
            )

            # If no results with language filter, try without
            if not results and filter_conditions:
                results = qdrant_manager.search(
                    collection_name="standards",
                    query_vector=query_vector,
                    top_k=self.top_k,
                )

            return _format_results(results), len(results)
        except Exception as e:
            return f"Error retrieving standards: {e}", 0

    def retrieve_adr_context(
        self, diff_text: str, service: str = ""
    ) -> tuple[str, int]:
        """Semantic search for relevant ADRs based on diff content."""
        if not diff_text.strip():
            return "No diff provided.", 0

        try:
            search_text = " ".join(diff_text.split()[:500])
            query_vector = embedding_service.embed_single(search_text)

            filter_conditions = {}
            if service:
                filter_conditions["service"] = service

            results = qdrant_manager.search(
                collection_name="adr",
                query_vector=query_vector,
                top_k=self.top_k,
                filter_conditions=filter_conditions if filter_conditions else None,
            )

            # Fallback without service filter
            if not results and filter_conditions:
                results = qdrant_manager.search(
                    collection_name="adr",
                    query_vector=query_vector,
                    top_k=self.top_k,
                )

            return _format_results(results), len(results)
        except Exception as e:
            return f"Error retrieving ADRs: {e}", 0

    def retrieve_history_context(
        self, diff_text: str, repo: str = ""
    ) -> tuple[str, int]:
        """Semantic search for similar past reviews."""
        if not diff_text.strip():
            return "No diff provided.", 0

        try:
            search_text = " ".join(diff_text.split()[:500])
            query_vector = embedding_service.embed_single(search_text)

            filter_conditions = {}
            if repo:
                filter_conditions["repo"] = repo

            results = qdrant_manager.search(
                collection_name="history",
                query_vector=query_vector,
                top_k=self.top_k,
                filter_conditions=filter_conditions if filter_conditions else None,
            )

            return _format_results(results), len(results)
        except Exception as e:
            return f"Error retrieving history: {e}", 0

    def retrieve_codebase_context(
        self, changed_files: list[str]
    ) -> tuple[str, int]:
        """Retrieve codebase context for changed files."""
        if not changed_files:
            return "No files changed.", 0

        try:
            # Create a search query from the changed file paths
            search_text = "Files changed: " + ", ".join(changed_files[:20])
            query_vector = embedding_service.embed_single(search_text)

            results = qdrant_manager.search(
                collection_name="codebase",
                query_vector=query_vector,
                top_k=self.top_k,
            )

            return _format_results(results), len(results)
        except Exception as e:
            return f"Error retrieving codebase context: {e}", 0

    def retrieve_all(
        self,
        diff_text: str,
        branch_name: str = "",
        pr_title: str = "",
        repo: str = "",
        author: str = "",
    ) -> ReviewContext:
        """
        Run all retrieval queries and return assembled ReviewContext.

        This is the main entry point for the review engine.
        """
        context = ReviewContext()

        # 1. Extract ticket ID
        ticket_id = extract_ticket_id(branch_name, pr_title)
        context.ticket_id = ticket_id or ""

        # 2. Detect language and service from diff
        language = _detect_language_from_diff(diff_text)
        changed_files = _extract_changed_files(diff_text)
        service = _extract_service_from_files(changed_files)

        console.print(f"  [dim]Language: {language} | Service: {service or 'N/A'} | "
                       f"Ticket: {ticket_id or 'N/A'} | Files: {len(changed_files)}[/dim]")

        # 3. Ticket context (exact match)
        context.ticket_context, context.matched_standards_count = \
            self.retrieve_ticket_context(ticket_id or "")

        # 4. Standards context (semantic search)
        context.standards_context, context.matched_standards_count = \
            self.retrieve_standards_context(diff_text, language)

        # 5. ADR context (semantic search)
        context.adr_context, context.matched_adr_count = \
            self.retrieve_adr_context(diff_text, service)

        # 6. History context (semantic search)
        context.history_context, context.matched_history_count = \
            self.retrieve_history_context(diff_text, repo)

        # 7. Codebase context (file-path based)
        context.codebase_context, context.matched_codebase_count = \
            self.retrieve_codebase_context(changed_files)

        # 8. Author context (from author registry)
        if author:
            from codeguard.ingestion.authors import author_registry
            context.author_guidance = author_registry.get_review_guidance(author)

        return context


# Module-level convenience instance
retriever = Retriever()
