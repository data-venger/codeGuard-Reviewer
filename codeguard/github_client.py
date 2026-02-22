"""
GitHub REST API client for CodeGuard.

Handles authenticated requests for PR listings, diffs, and review comments.
"""

import time
from typing import Any, Optional

import requests
from rich.console import Console

from config.settings import settings

console = Console()


class GitHubClient:
    """Authenticated GitHub REST API client with rate-limit handling."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = settings.github_token):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make a request with rate-limit retry handling."""
        url = f"{self.BASE_URL}{path}"
        resp = self.session.request(method, url, **kwargs)

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_time - int(time.time()), 1)
            console.print(f"  [yellow]Rate limited. Waiting {wait}s...[/yellow]")
            time.sleep(min(wait, 60))  # Cap wait at 60s
            resp = self.session.request(method, url, **kwargs)

        resp.raise_for_status()
        return resp

    # ── Repository Operations ──

    def list_repos(self, org: str = settings.github_org) -> list[dict[str, Any]]:
        """List all repositories for an organisation."""
        repos = []
        page = 1
        while True:
            resp = self._request("GET", f"/orgs/{org}/repos", params={
                "per_page": 100,
                "page": page,
                "type": "all",
            })
            data = resp.json()
            if not data:
                break
            repos.extend(data)
            page += 1
        return repos

    # ── PR Operations ──

    def list_open_prs(
        self, owner: str, repo: str, state: str = "open"
    ) -> list[dict[str, Any]]:
        """List open pull requests for a repository."""
        prs = []
        page = 1
        while True:
            resp = self._request("GET", f"/repos/{owner}/{repo}/pulls", params={
                "state": state,
                "per_page": 100,
                "page": page,
            })
            data = resp.json()
            if not data:
                break
            prs.extend(data)
            page += 1
        return prs

    def get_pr(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Get a single PR's metadata."""
        resp = self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        return resp.json()

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Fetch the raw .patch diff for a PR.

        Uses the diff media type to get the unified diff format.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = self.session.get(
            url,
            headers={
                **self.session.headers,
                "Accept": "application/vnd.github.v3.diff",
            },
        )
        resp.raise_for_status()
        return resp.text

    def get_pr_review_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Fetch all review comments on a PR."""
        comments = []
        page = 1
        while True:
            resp = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                params={"per_page": 100, "page": page},
            )
            data = resp.json()
            if not data:
                break
            comments.extend(data)
            page += 1
        return comments

    def get_pr_reviews(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Fetch all reviews (approved, changes_requested, etc.) on a PR."""
        resp = self._request(
            "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        )
        return resp.json()

    # ── Closed / Merged PRs (for history ingestion) ──

    def list_closed_prs(
        self,
        owner: str,
        repo: str,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """
        List recently closed/merged PRs for historical review ingestion.

        Limited to max_pages to avoid pulling entire history.
        """
        prs = []
        for page in range(1, max_pages + 1):
            resp = self._request("GET", f"/repos/{owner}/{repo}/pulls", params={
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": 50,
                "page": page,
            })
            data = resp.json()
            if not data:
                break
            prs.extend(data)
        return prs
