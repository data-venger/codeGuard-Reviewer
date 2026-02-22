#!/usr/bin/env python3
"""
CodeGuard Ingestion CLI.

Run all or individual ingestion pipelines to populate the Qdrant vector database
with organisational context.

Usage:
    python scripts/ingest.py all          # Run all pipelines
    python scripts/ingest.py standards    # Standards only
    python scripts/ingest.py adrs         # ADRs only
    python scripts/ingest.py tickets      # Plane tickets only
    python scripts/ingest.py history      # GitHub PR history only
    python scripts/ingest.py codebase     # Codebase context only
    python scripts/ingest.py authors      # Load author profiles only
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def cli():
    """CodeGuard — Context Ingestion Pipeline"""
    pass


@cli.command()
def all():
    """Run all ingestion pipelines in sequence."""
    console.print(Panel.fit(
        "[bold magenta]CodeGuard — Full Ingestion Run[/bold magenta]",
        border_style="magenta",
    ))

    results = {}

    # 1. Standards
    from codeguard.ingestion.standards import ingest_standards
    results["Standards"] = ingest_standards()

    # 2. ADRs
    from codeguard.ingestion.adrs import ingest_adrs
    results["ADRs"] = ingest_adrs()

    # 3. Tickets (may fail if Plane not configured)
    from codeguard.ingestion.tickets import ingest_tickets
    results["Tickets"] = ingest_tickets()

    # 4. History (may fail if GitHub not configured)
    from codeguard.ingestion.history import ingest_history
    results["History"] = ingest_history()

    # 5. Authors
    from codeguard.ingestion.authors import author_registry
    results["Authors"] = author_registry.load()

    # Summary table
    console.print()
    table = Table(title="Ingestion Summary", border_style="green")
    table.add_column("Pipeline", style="cyan")
    table.add_column("Chunks / Profiles", style="green", justify="right")
    for name, count in results.items():
        table.add_row(name, str(count))
    console.print(table)


@cli.command()
def standards():
    """Ingest coding standards from Markdown files."""
    from codeguard.ingestion.standards import ingest_standards
    count = ingest_standards()
    console.print(f"\n[bold]Total: {count} chunks[/bold]")


@cli.command()
def adrs():
    """Ingest Architecture Decision Records."""
    from codeguard.ingestion.adrs import ingest_adrs
    count = ingest_adrs()
    console.print(f"\n[bold]Total: {count} chunks[/bold]")


@cli.command()
def tickets():
    """Ingest tickets from Plane."""
    from codeguard.ingestion.tickets import ingest_tickets
    count = ingest_tickets()
    console.print(f"\n[bold]Total: {count} chunks[/bold]")


@cli.command()
def history():
    """Ingest historical PR review comments from GitHub."""
    from codeguard.ingestion.history import ingest_history
    count = ingest_history()
    console.print(f"\n[bold]Total: {count} chunks[/bold]")


@cli.command()
@click.argument("paths", nargs=-1, required=True)
def codebase(paths):
    """Ingest codebase context from repository directories."""
    from codeguard.ingestion.codebase import ingest_codebase
    count = ingest_codebase(list(paths))
    console.print(f"\n[bold]Total: {count} chunks[/bold]")


@cli.command()
def authors():
    """Load author profiles from YAML."""
    from codeguard.ingestion.authors import author_registry
    count = author_registry.load()
    console.print(f"\n[bold]Total: {count} profiles loaded[/bold]")


if __name__ == "__main__":
    cli()
