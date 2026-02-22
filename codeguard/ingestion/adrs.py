"""
Layer 3 — Architecture Decision Record (ADR) Ingestion.

Scans ADR Markdown files, chunks them by headings,
embeds, and upserts into the Qdrant 'adr' collection.
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


def _parse_adr_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from ADR file."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta, parts[2]
            except yaml.YAMLError:
                pass
    return {}, content


def _extract_adr_number(filename: str) -> str:
    """Extract ADR number from filename (e.g., 'adr-012-use-repo-pattern.md' → 'ADR-012')."""
    match = re.match(r"(?:adr[_-]?)(\d+)", filename.lower())
    if match:
        return f"ADR-{match.group(1).zfill(3)}"
    return ""


def _detect_status(content: str, frontmatter: dict) -> str:
    """Detect ADR status from frontmatter or content."""
    if "status" in frontmatter:
        return str(frontmatter["status"]).lower()

    content_lower = content.lower()
    if "status: accepted" in content_lower or "## accepted" in content_lower:
        return "accepted"
    if "status: superseded" in content_lower:
        return "superseded"
    if "status: deprecated" in content_lower:
        return "deprecated"
    if "status: proposed" in content_lower:
        return "proposed"
    return "accepted"  # Default assumption


def _detect_date(content: str, frontmatter: dict) -> str:
    """Extract date from frontmatter or content."""
    if "date" in frontmatter:
        return str(frontmatter["date"])

    # Try to find a date pattern in the first few lines
    date_match = re.search(r"\d{4}-\d{2}(-\d{2})?", content[:500])
    if date_match:
        return date_match.group(0)
    return ""


def ingest_adrs(adrs_dir: Path | None = None) -> int:
    """
    Ingest all ADR Markdown files.

    Args:
        adrs_dir: Override directory (defaults to settings.adrs_path).

    Returns:
        Total number of chunks upserted.
    """
    target_dir = adrs_dir or settings.adrs_path

    console.print(f"\n[bold]🏛️  Ingesting ADRs from {target_dir}...[/bold]")

    if not target_dir.exists():
        console.print(f"  [yellow]Directory not found: {target_dir}[/yellow]")
        console.print("  [dim]Create it and add ADR .md files, then re-run.[/dim]")
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
        frontmatter, body = _parse_adr_frontmatter(content)

        adr_number = _extract_adr_number(md_file.stem)
        status = _detect_status(content, frontmatter)
        date = _detect_date(content, frontmatter)

        base_metadata = {
            "type": "adr",
            "adr_id": adr_number or md_file.stem,
            "service": frontmatter.get("service", ""),
            "status": status,
            "date": date,
            "source_file": str(relative),
            "tags": ",".join(frontmatter.get("tags", [])) if "tags" in frontmatter else "",
        }

        chunks = chunk_markdown_by_headings(body, max_tokens=300, source_metadata=base_metadata)

        if not chunks:
            console.print("    [dim]No chunks produced.[/dim]")
            continue

        all_texts = [c.text for c in chunks]
        all_metadata = [c.metadata for c in chunks]

        console.print(f"    Embedding {len(all_texts)} chunks...")
        vectors = embedding_service.embed_texts(all_texts)
        count = qdrant_manager.upsert_points("adr", all_texts, vectors, all_metadata)
        total_upserted += count
        console.print(f"    [green]✓ {count} chunks upserted[/green]")

    console.print(f"\n[bold green]✓ ADR ingestion complete: {total_upserted} total chunks[/bold green]")
    return total_upserted
