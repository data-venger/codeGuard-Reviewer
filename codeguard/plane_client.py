"""
Plane REST API client for CodeGuard.

Handles authenticated requests to Plane (open-source Jira alternative)
for fetching project issues, descriptions, and comments.
"""

from typing import Any

import requests
from rich.console import Console

from config.settings import settings

console = Console()


class PlaneClient:
    """Authenticated Plane REST API client."""

    def __init__(
        self,
        base_url: str = settings.plane_base_url,
        token: str = settings.plane_api_token,
        workspace_slug: str = settings.plane_workspace_slug,
    ):
        self.base_url = base_url.rstrip("/")
        self.workspace_slug = workspace_slug
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": token,
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make a request to the Plane API."""
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Project Operations ──

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects in the configured workspace."""
        resp = self._request(
            "GET",
            f"/workspaces/{self.workspace_slug}/projects/",
        )
        data = resp.json()
        # Plane API may return results nested under a 'results' key
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data if isinstance(data, list) else []

    # ── Issue Operations ──

    def list_issues(
        self, project_id: str, max_pages: int = 10
    ) -> list[dict[str, Any]]:
        """
        List all issues for a project.

        Handles pagination to fetch all issues up to max_pages.
        """
        issues = []
        cursor = None

        for _ in range(max_pages):
            params = {"per_page": 100}
            if cursor:
                params["cursor"] = cursor

            resp = self._request(
                "GET",
                f"/workspaces/{self.workspace_slug}/projects/{project_id}/issues/",
                params=params,
            )
            data = resp.json()

            if isinstance(data, dict):
                results = data.get("results", [])
                issues.extend(results)
                cursor = data.get("next_cursor")
                if not cursor:
                    break
            elif isinstance(data, list):
                issues.extend(data)
                break

        return issues

    def get_issue(self, project_id: str, issue_id: str) -> dict[str, Any]:
        """Get a single issue's full details."""
        resp = self._request(
            "GET",
            f"/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/",
        )
        return resp.json()

    def get_issue_comments(
        self, project_id: str, issue_id: str
    ) -> list[dict[str, Any]]:
        """Get all comments on an issue."""
        resp = self._request(
            "GET",
            f"/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/comments/",
        )
        data = resp.json()
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data if isinstance(data, list) else []
