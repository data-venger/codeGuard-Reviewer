"""
Layer 2 — Coding Standards Ingestion.

Recursively scans Markdown files in the standards directory,
chunks them by headings, embeds, and upserts into Qdrant 'standards' collection.
"""

import re
from pathlib import Path

import yaml
from rich.console import Console

from codeguard.chunker import chunk_markdown_by_headings
from codeguard.embeddings import embedding_service
from codeguard.qdrant_store import qdrant_manager
from config.settings import settings

console = Console()

# Language detection based on filename or frontmatter
LANGUAGE_PATTERNS = {
    "python": ["python", "py", "django", "flask", "fastapi"],
    "javascript": ["javascript", "js", "node", "react", "next"],
    "typescript": ["typescript", "ts", "angular"],
    "java": ["java", "spring", "maven"],
    "go": ["go", "golang"],
    "rust": ["rust", "cargo"],
    "sql": ["sql", "database", "db"],
    "general": ["general", "contributing", "common"],
}

# Category detection from heading or content
CATEGORY_KEYWORDS = {
    "security": ["security", "auth", "csrf", "xss", "injection", "secret", "encryption", "ssl"],
    "testing": ["test", "coverage", "mock", "fixture", "assertion", "unit test", "integration"],
    "error_handling": ["error", "exception", "try", "catch", "logging", "log"],
    "naming": ["naming", "convention", "camelcase", "snake_case", "variable", "function name"],
    "architecture": ["architecture", "pattern", "layer", "module", "dependency", "import"],
    "performance": ["performance", "optimization", "cache", "memory", "latency"],
    "formatting": ["format", "indent", "whitespace", "line length", "style"],
    "documentation": ["docstring", "comment", "documentation", "readme", "jsdoc"],
}


def _detect_language(filename: str, content: str) -> str:
    """Infer programming language from filename or YAML frontmatter."""
    name_lower = filename.lower()
    for lang, patterns in LANGUAGE_PATTERNS.items():
        if any(p in name_lower for p in patterns):
            return lang
    return "general"


def _detect_category(text: str) -> str:
    """Infer rule category from chunk text content."""
    text_lower = text.lower()
    best_category = "general"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def _detect_severity(text: str) -> str:
    """Infer severity from content keywords."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["must", "required", "never", "always", "error", "critical"]):
        return "error"
    if any(w in text_lower for w in ["should", "recommended", "warning", "prefer"]):
        return "warning"
    return "info"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter if present. Returns (metadata, remaining_content)."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta, parts[2]
            except yaml.YAMLError:
                pass
    return {}, content


def ingest_standards(standards_dir: Path | None = None) -> int:
    """
    Ingest all coding standards Markdown files.

    Args:
        standards_dir: Override directory (defaults to settings.standards_path).

    Returns:
        Total number of chunks upserted.
    """
    target_dir = standards_dir or settings.standards_path

    console.print(f"\n[bold]📏 Ingesting coding standards from {target_dir}...[/bold]")

    if not target_dir.exists():
        console.print(f"  [yellow]Directory not found: {target_dir}[/yellow]")
        console.print("  [dim]Create it and add .md files, then re-run.[/dim]")
        return 0

    md_files = sorted(target_dir.rglob("*.md"))
    if not md_files:
        console.print("  [dim]No .md files found.[/dim]")
        return 0

    total_upserted = 0

    for md_file in md_files:
        relative = md_file.relative_to(target_dir)
        console.print(f"\n  [cyan]{relative}[/cyan]")

        content = md_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(content)

        # Detect language from frontmatter override or filename
        language = frontmatter.get("language", _detect_language(md_file.name, body))

        base_metadata = {
            "type": "standard",
            "language": language,
            "source_file": str(relative),
        }

        # Override metadata from frontmatter if provided
        if "category" in frontmatter:
            base_metadata["category"] = frontmatter["category"]
        if "severity" in frontmatter:
            base_metadata["severity"] = frontmatter["severity"]

        chunks = chunk_markdown_by_headings(body, max_tokens=300, source_metadata=base_metadata)

        if not chunks:
            console.print("    [dim]No chunks produced (file may be empty).[/dim]")
            continue

        # Enrich each chunk with auto-detected category and severity
        all_texts = []
        all_metadata = []
        for chunk in chunks:
            meta = {**chunk.metadata}
            if "category" not in meta:
                meta["category"] = _detect_category(chunk.text)
            if "severity" not in meta:
                meta["severity"] = _detect_severity(chunk.text)
            all_texts.append(chunk.text)
            all_metadata.append(meta)

        console.print(f"    Embedding {len(all_texts)} chunks...")
        vectors = embedding_service.embed_texts(all_texts)
        count = qdrant_manager.upsert_points("standards", all_texts, vectors, all_metadata)
        total_upserted += count
        console.print(f"    [green]✓ {count} chunks upserted[/green]")

    console.print(f"\n[bold green]✓ Standards ingestion complete: {total_upserted} total chunks[/bold green]")
    return total_upserted
