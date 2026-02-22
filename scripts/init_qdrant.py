#!/usr/bin/env python3
"""
One-time Qdrant collection initialization.

Creates all 5 collections with the correct vector configuration.
Safe to re-run — skips existing collections.

Usage:
    python scripts/init_qdrant.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel

from codeguard.qdrant_store import qdrant_manager

console = Console()


def main():
    console.print(Panel.fit(
        "[bold cyan]CodeGuard — Qdrant Collection Initialisation[/bold cyan]",
        border_style="cyan",
    ))

    try:
        results = qdrant_manager.init_collections()
    except Exception as e:
        console.print(f"\n[red]✗ Failed to connect to Qdrant: {e}[/red]")
        console.print("[dim]Is Qdrant running? Try: docker compose up -d[/dim]")
        sys.exit(1)

    created = sum(1 for v in results.values() if v == "created")
    existing = sum(1 for v in results.values() if v == "exists")

    console.print(f"\n[green]✓ Done: {created} created, {existing} already existed[/green]")


if __name__ == "__main__":
    main()
