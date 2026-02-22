"""
LangChain tools for the CodeGuard agent.

Each tool wraps an existing module and provides a clean interface
for the LLM agent to call via tool routing.
"""

import json
from typing import Optional

from langchain_core.tools import tool

from config.settings import settings


@tool
def list_open_prs(
    repo: Optional[str] = None,
    org: Optional[str] = None,
) -> str:
    """List open pull requests for a GitHub repository.
    
    Use this when the user asks to see PRs, list PRs, or show pull requests.
    
    Args:
        repo: Repository name. Defaults to the configured repo.
        org: GitHub org/owner. Defaults to the configured org.
    """
    from codeguard.github_client import GitHubClient

    owner = org or settings.github_org
    repository = repo or (
        settings.github_repos_list[0] if settings.github_repos_list else ""
    )

    if not owner or not repository:
        return "⚠️ No repository configured. Please set GITHUB_ORG and GITHUB_REPOS in .env"

    try:
        client = GitHubClient()
        prs = client.list_open_prs(owner, repository)

        if not prs:
            return f"No open pull requests found in {owner}/{repository}."

        lines = [f"**Open PRs in {owner}/{repository}** ({len(prs)} total):\n"]
        for pr in prs[:15]:  # Limit to 15 for readability
            number = pr.get("number", "?")
            title = pr.get("title", "Untitled")
            author = pr.get("user", {}).get("login", "?")
            branch = pr.get("head", {}).get("ref", "")
            lines.append(
                f"- **#{number}** — {title} (by `{author}`, branch: `{branch}`)"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error listing PRs: {e}"


@tool
def review_pr(
    pr_number: int,
    repo: Optional[str] = None,
    org: Optional[str] = None,
) -> str:
    """Run a full AI code review on a specific pull request.
    
    Use this when the user asks to review a PR, check a PR, or analyze a pull request.
    The review includes ticket compliance, standards violations, architecture checks,
    bugs/edge cases, and improvements.
    
    Args:
        pr_number: The PR number to review (e.g. 5 for PR #5).
        repo: Repository name. Defaults to the configured repo.
        org: GitHub org/owner. Defaults to the configured org.
    """
    from codeguard.review_engine import ReviewEngine

    owner = org or settings.github_org
    repository = repo or (
        settings.github_repos_list[0] if settings.github_repos_list else ""
    )

    if not owner or not repository:
        return "⚠️ No repository configured."

    try:
        engine = ReviewEngine()
        result = engine.review_pr(
            owner=owner,
            repo=repository,
            pr_number=pr_number,
            stream=False,
        )

        summary = [
            f"## Review: PR #{result.pr_number} — {result.pr_title}",
            f"**Verdict**: {result.verdict} {result.verdict_emoji}",
            f"**Duration**: {result.duration_seconds:.1f}s | **Model**: {result.model_used}",
            "",
            result.review_markdown,
        ]
        return "\n".join(summary)
    except Exception as e:
        return f"❌ Error reviewing PR: {e}"


@tool
def search_standards(query: str) -> str:
    """Search the organisation's coding standards for rules and conventions.
    
    Use this when the user asks about coding rules, naming conventions,
    style guidelines, best practices, or any coding standard.
    
    Args:
        query: The search query describing what standards to find (e.g. "Python naming conventions", "error handling rules").
    """
    from codeguard.embeddings import embedding_service
    from codeguard.qdrant_store import qdrant_manager

    try:
        vector = embedding_service.embed_single(query)
        results = qdrant_manager.search(
            collection_name="standards",
            query_vector=vector,
            top_k=5,
        )

        if not results:
            return "No matching coding standards found."

        lines = [f"**Coding Standards matching: \"{query}\"**\n"]
        for i, r in enumerate(results, 1):
            text = r.get("text", "")
            score = r.get("score", 0)
            meta = r.get("metadata", {})
            source = meta.get("source_file", "")
            lines.append(f"### [{i}] {source} (relevance: {score:.2f})")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error searching standards: {e}"


@tool
def search_history(query: str) -> str:
    """Search past PR review comments and feedback from historical reviews.
    
    Use this when the user asks about past reviews, previous feedback,
    what was flagged before, or historical review patterns.
    
    Args:
        query: The search query (e.g. "error handling", "null checks", "authentication issues").
    """
    from codeguard.embeddings import embedding_service
    from codeguard.qdrant_store import qdrant_manager

    try:
        vector = embedding_service.embed_single(query)
        results = qdrant_manager.search(
            collection_name="history",
            query_vector=vector,
            top_k=5,
        )

        if not results:
            return "No matching historical reviews found."

        lines = [f"**Past Reviews matching: \"{query}\"**\n"]
        for i, r in enumerate(results, 1):
            text = r.get("text", "")
            score = r.get("score", 0)
            meta = r.get("metadata", {})
            pr_id = meta.get("pr_id", "?")
            repo = meta.get("repo", "?")
            verdict = meta.get("verdict", "")
            lines.append(
                f"### [{i}] PR #{pr_id} in {repo} — {verdict} (relevance: {score:.2f})"
            )
            lines.append(text)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error searching history: {e}"


@tool
def search_adrs(query: str) -> str:
    """Search Architecture Decision Records (ADRs) for design patterns and decisions.
    
    Use this when the user asks about architecture decisions, design patterns,
    ADRs, or architectural guidelines.
    
    Args:
        query: The search query (e.g. "repository pattern", "database design", "API conventions").
    """
    from codeguard.embeddings import embedding_service
    from codeguard.qdrant_store import qdrant_manager

    try:
        vector = embedding_service.embed_single(query)
        results = qdrant_manager.search(
            collection_name="adr",
            query_vector=vector,
            top_k=5,
        )

        if not results:
            return "No matching ADRs found."

        lines = [f"**ADRs matching: \"{query}\"**\n"]
        for i, r in enumerate(results, 1):
            text = r.get("text", "")
            score = r.get("score", 0)
            meta = r.get("metadata", {})
            source = meta.get("source_file", "")
            status = meta.get("status", "")
            lines.append(
                f"### [{i}] {source} — {status} (relevance: {score:.2f})"
            )
            lines.append(text)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error searching ADRs: {e}"


# All tools for agent registration
ALL_TOOLS = [
    list_open_prs,
    review_pr,
    search_standards,
    search_history,
    search_adrs,
]
