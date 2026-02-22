"""
Layer 4 — Historical PR Review Ingestion.

Fetches past PR review comments from GitHub, packages each as a chunk,
embeds, and upserts into the Qdrant 'history' collection.
"""

from rich.console import Console
from rich.progress import Progress

from codeguard.chunker import chunk_review_comment
from codeguard.embeddings import embedding_service
from codeguard.github_client import GitHubClient
from codeguard.qdrant_store import qdrant_manager
from config.settings import settings

console = Console()


def _determine_verdict(reviews: list[dict], pr_state: str) -> str:
    """Determine overall verdict from PR reviews and state."""
    if not reviews:
        return "no_review"

    states = {r.get("state", "").lower() for r in reviews}
    if "changes_requested" in states:
        return "changes_requested"
    if "approved" in states:
        return "approved"
    if pr_state == "closed":
        return "closed_without_merge"
    return "commented"


def ingest_history(
    owner: str | None = None,
    repos: list[str] | None = None,
    max_prs_per_repo: int = 50,
) -> int:
    """
    Ingest historical PR review comments from GitHub.

    Fetches closed/merged PRs and their review comments, stores each
    comment as a separate chunk in the 'history' collection.

    Args:
        owner: GitHub org/owner (defaults to settings.github_org).
        repos: List of repos (defaults to settings.github_repos_list).
        max_prs_per_repo: Maximum closed PRs to process per repo.

    Returns:
        Total number of chunks upserted.
    """
    owner = owner or settings.github_org
    repos = repos or settings.github_repos_list

    if not owner or not repos:
        console.print("\n[yellow]⚠ GitHub org/repos not configured. Skipping history ingestion.[/yellow]")
        console.print("  [dim]Set GITHUB_ORG and GITHUB_REPOS in .env[/dim]")
        return 0

    client = GitHubClient()
    total_upserted = 0

    console.print(f"\n[bold]📜 Ingesting PR review history from GitHub ({owner})...[/bold]")

    for repo in repos:
        console.print(f"\n  [cyan]Repo: {owner}/{repo}[/cyan]")

        try:
            closed_prs = client.list_closed_prs(owner, repo, max_pages=max_prs_per_repo // 50 + 1)
        except Exception as e:
            console.print(f"    [red]✗ Failed to fetch PRs: {e}[/red]")
            continue

        # Limit to max_prs_per_repo
        closed_prs = closed_prs[:max_prs_per_repo]
        console.print(f"    Found {len(closed_prs)} closed PRs")

        all_texts = []
        all_metadata = []

        with Progress() as progress:
            task = progress.add_task(f"    Processing PRs", total=len(closed_prs))

            for pr in closed_prs:
                pr_number = pr.get("number", 0)
                pr_author = pr.get("user", {}).get("login", "unknown")
                pr_date = pr.get("closed_at", pr.get("updated_at", ""))
                pr_state = pr.get("state", "")

                try:
                    # Fetch review comments (inline comments on code)
                    comments = client.get_pr_review_comments(owner, repo, pr_number)

                    # Fetch reviews (approve/reject decisions)
                    reviews = client.get_pr_reviews(owner, repo, pr_number)
                    verdict = _determine_verdict(reviews, pr_state)

                    for comment in comments:
                        comment_body = comment.get("body", "")
                        if not comment_body or len(comment_body.strip()) < 10:
                            continue  # Skip trivial comments

                        file_path = comment.get("path", "")
                        comment_author = comment.get("user", {}).get("login", "")

                        chunk = chunk_review_comment(
                            comment_body=comment_body,
                            pr_id=pr_number,
                            author=comment_author or pr_author,
                            repo=repo,
                            verdict=verdict,
                            date=pr_date[:10] if pr_date else "",
                            file_path=file_path,
                        )

                        all_texts.append(chunk.text)
                        all_metadata.append(chunk.metadata)

                except Exception as e:
                    console.print(f"    [dim]Skipping PR #{pr_number}: {e}[/dim]")

                progress.advance(task)

        if all_texts:
            console.print(f"    Embedding {len(all_texts)} review comments...")
            vectors = embedding_service.embed_texts(all_texts)
            count = qdrant_manager.upsert_points("history", all_texts, vectors, all_metadata)
            total_upserted += count
            console.print(f"    [green]✓ {count} chunks upserted[/green]")
        else:
            console.print("    [dim]No review comments found.[/dim]")

    console.print(f"\n[bold green]✓ History ingestion complete: {total_upserted} total chunks[/bold green]")
    return total_upserted
