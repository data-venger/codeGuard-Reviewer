"""
Layer 1 — Ticket Intent Ingestion (Plane API).

Fetches issues from Plane, chunks them using the two-chunk strategy,
embeds and upserts into the Qdrant 'tickets' collection.
"""

from rich.console import Console
from rich.progress import Progress

from codeguard.chunker import chunk_ticket
from codeguard.embeddings import embedding_service
from codeguard.plane_client import PlaneClient
from codeguard.qdrant_store import qdrant_manager

console = Console()


def ingest_tickets() -> int:
    """
    Ingest all tickets from configured Plane projects.

    Returns:
        Total number of chunks upserted.
    """
    client = PlaneClient()
    total_upserted = 0

    console.print("\n[bold]📋 Ingesting tickets from Plane...[/bold]")

    try:
        projects = client.list_projects()
    except Exception as e:
        console.print(f"  [red]✗ Failed to fetch projects: {e}[/red]")
        console.print("  [dim]Skipping ticket ingestion. Check PLANE_* env vars.[/dim]")
        return 0

    if not projects:
        console.print("  [yellow]No projects found in workspace.[/yellow]")
        return 0

    for project in projects:
        project_id = project.get("id", "")
        project_name = project.get("name", project.get("identifier", "unknown"))
        console.print(f"\n  [cyan]Project: {project_name}[/cyan]")

        try:
            issues = client.list_issues(project_id)
        except Exception as e:
            console.print(f"    [red]✗ Failed to fetch issues: {e}[/red]")
            continue

        if not issues:
            console.print("    [dim]No issues found.[/dim]")
            continue

        all_texts = []
        all_metadata = []

        with Progress() as progress:
            task = progress.add_task(f"    Chunking {len(issues)} issues", total=len(issues))

            for issue in issues:
                issue_key = issue.get("sequence_id", issue.get("id", ""))
                project_identifier = project.get("identifier", "")
                full_key = f"{project_identifier}-{issue_key}" if project_identifier else str(issue_key)

                title = issue.get("name", "")
                description = issue.get("description_stripped", issue.get("description", ""))
                priority = issue.get("priority", "none")
                status_detail = issue.get("state_detail", {})
                status = status_detail.get("name", "") if isinstance(status_detail, dict) else ""

                # Fetch comments for this issue
                comments_text = ""
                try:
                    comments = client.get_issue_comments(project_id, issue.get("id", ""))
                    if comments:
                        comments_text = "\n\n".join(
                            c.get("comment_stripped", c.get("comment", ""))
                            for c in comments
                            if c.get("comment_stripped") or c.get("comment")
                        )
                except Exception:
                    pass  # Comments are optional context

                # Extract acceptance criteria from description if present
                acceptance = ""
                if description:
                    # Try to find AC section in description
                    lower_desc = description.lower()
                    for marker in ["acceptance criteria", "ac:", "definition of done"]:
                        idx = lower_desc.find(marker)
                        if idx != -1:
                            acceptance = description[idx:]
                            description = description[:idx]
                            break

                chunks = chunk_ticket(
                    title=title,
                    description=description,
                    acceptance_criteria=acceptance,
                    comments=comments_text,
                    issue_key=full_key,
                    project=project_name,
                    status=status,
                    priority=str(priority),
                )

                for chunk in chunks:
                    all_texts.append(chunk.text)
                    all_metadata.append(chunk.metadata)

                progress.advance(task)

        if all_texts:
            console.print(f"    Embedding {len(all_texts)} chunks...")
            vectors = embedding_service.embed_texts(all_texts)
            count = qdrant_manager.upsert_points("tickets", all_texts, vectors, all_metadata)
            total_upserted += count
            console.print(f"    [green]✓ Upserted {count} chunks[/green]")

    console.print(f"\n[bold green]✓ Ticket ingestion complete: {total_upserted} total chunks[/bold green]")
    return total_upserted
