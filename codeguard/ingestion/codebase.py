"""
Layer 5 — Codebase Context Ingestion.

Generates plain-language module summaries from README files and key
source files, then embeds and upserts to Qdrant 'codebase' collection.
"""

import os
from pathlib import Path

from rich.console import Console

from codeguard.chunker import chunk_markdown_by_headings
from codeguard.embeddings import embedding_service
from codeguard.qdrant_store import qdrant_manager

console = Console()

# File patterns to look for in each repo/service directory
CONTEXT_FILES = [
    "README.md",
    "readme.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "docs/README.md",
]

# Source file extensions to generate brief summaries for
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".rs"}


def _generate_file_summary(file_path: Path) -> str:
    """
    Generate a plain-language summary of a source file.

    Extracts the module docstring, class names, and function signatures
    to create a concise description. Does NOT embed the full source code.
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    lines = content.split("\n")
    summary_parts = [f"File: {file_path.name}"]

    # Extract module docstring (Python-style)
    if file_path.suffix == ".py":
        in_docstring = False
        docstring_lines = []
        for line in lines[:30]:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    docstring_lines.append(stripped.rstrip('"""').rstrip("'''"))
                    break
                else:
                    in_docstring = True
                    remaining = stripped[3:]
                    if remaining.endswith('"""') or remaining.endswith("'''"):
                        docstring_lines.append(remaining[:-3])
                        break
                    docstring_lines.append(remaining)
            elif in_docstring:
                docstring_lines.append(stripped)

        if docstring_lines:
            summary_parts.append("Description: " + " ".join(docstring_lines).strip())

    # Extract class and function names
    classes = []
    functions = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("class ") and "(" in stripped:
            class_name = stripped.split("(")[0].replace("class ", "").strip()
            classes.append(class_name)
        elif stripped.startswith("def ") and "(" in stripped:
            func_name = stripped.split("(")[0].replace("def ", "").strip()
            if not func_name.startswith("_"):
                functions.append(func_name)

    if classes:
        summary_parts.append(f"Classes: {', '.join(classes[:10])}")
    if functions:
        summary_parts.append(f"Public functions: {', '.join(functions[:15])}")
    summary_parts.append(f"Lines: {len(lines)}")

    return "\n".join(summary_parts)


def ingest_codebase(repo_paths: list[str | Path] | None = None) -> int:
    """
    Ingest codebase context from repository directories.

    Processes README files and generates module summaries for key source files.

    Args:
        repo_paths: List of repository root directories to scan.
                    If None, looks for repos under common locations.

    Returns:
        Total number of chunks upserted.
    """
    console.print("\n[bold]💻 Ingesting codebase context...[/bold]")

    if not repo_paths:
        console.print("  [yellow]No repository paths configured.[/yellow]")
        console.print("  [dim]Pass repo_paths or configure in settings.[/dim]")
        return 0

    total_upserted = 0

    for repo_path in repo_paths:
        repo_path = Path(repo_path)
        if not repo_path.exists():
            console.print(f"  [yellow]Path not found: {repo_path}[/yellow]")
            continue

        service_name = repo_path.name
        console.print(f"\n  [cyan]Service: {service_name}[/cyan]")

        all_texts = []
        all_metadata = []

        # 1. Ingest README and documentation files
        for context_file in CONTEXT_FILES:
            target = repo_path / context_file
            if target.exists():
                console.print(f"    Processing {context_file}...")
                content = target.read_text(encoding="utf-8")

                chunks = chunk_markdown_by_headings(
                    content,
                    max_tokens=300,
                    source_metadata={
                        "type": "codebase",
                        "service": service_name,
                        "file_path": context_file,
                        "content_type": "documentation",
                    },
                )

                for chunk in chunks:
                    all_texts.append(chunk.text)
                    all_metadata.append(chunk.metadata)

        # 2. Generate summaries for key source files
        source_count = 0
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden dirs, node_modules, venvs, etc.
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in {"node_modules", "venv", "__pycache__", "dist", "build"}
            ]

            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix in SOURCE_EXTENSIONS and source_count < 100:
                    summary = _generate_file_summary(fpath)
                    if summary and len(summary) > 50:
                        relative = str(fpath.relative_to(repo_path))
                        all_texts.append(summary)
                        all_metadata.append({
                            "type": "codebase",
                            "service": service_name,
                            "file_path": relative,
                            "content_type": "file_summary",
                        })
                        source_count += 1

        if all_texts:
            console.print(f"    Embedding {len(all_texts)} chunks...")
            vectors = embedding_service.embed_texts(all_texts)
            count = qdrant_manager.upsert_points("codebase", all_texts, vectors, all_metadata)
            total_upserted += count
            console.print(f"    [green]✓ {count} chunks upserted[/green]")
        else:
            console.print("    [dim]No context files found.[/dim]")

    console.print(f"\n[bold green]✓ Codebase ingestion complete: {total_upserted} total chunks[/bold green]")
    return total_upserted
