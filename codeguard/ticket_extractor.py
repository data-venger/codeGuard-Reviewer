"""
Ticket ID Extractor for CodeGuard.

Extracts ticket/issue identifiers from PR branch names and titles
using regex patterns. Supports common formats like APP-123, FEAT-45, BUG-7.
"""

import re


# Patterns to match ticket IDs — ordered by specificity
TICKET_PATTERNS = [
    # Standard project-key format: APP-123, FEAT-45, BUG-7, PROJ-1234
    re.compile(r"\b([A-Z]{2,10}-\d+)\b"),
    # Lowercase with separator: feature/app-123-description, bugfix/bug-45
    re.compile(r"(?:^|/)([a-zA-Z]{2,10}-\d+)(?:-|/|$)", re.IGNORECASE),
]

# Common branch prefixes to strip before matching
BRANCH_PREFIXES = [
    "feature/", "feat/", "bugfix/", "fix/", "hotfix/",
    "release/", "chore/", "refactor/", "docs/",
]


def extract_ticket_id(
    branch_name: str = "",
    pr_title: str = "",
) -> str | None:
    """
    Extract a ticket ID from a PR branch name or title.

    Tries the branch name first (most reliable), falls back to PR title.
    Returns the first match found, normalised to uppercase.

    Args:
        branch_name: Git branch name (e.g. "feature/APP-183-add-login")
        pr_title: PR title (e.g. "[APP-183] Add user login")

    Returns:
        Ticket ID string (e.g. "APP-183") or None if not found.

    Examples:
        >>> extract_ticket_id("feature/APP-183-add-login")
        'APP-183'
        >>> extract_ticket_id("", "[FEAT-42] Implement search")
        'FEAT-42'
        >>> extract_ticket_id("main")
        None
    """
    # Try branch name first
    for source in [branch_name, pr_title]:
        if not source:
            continue
        for pattern in TICKET_PATTERNS:
            match = pattern.search(source)
            if match:
                return match.group(1).upper()

    return None


def extract_all_ticket_ids(
    branch_name: str = "",
    pr_title: str = "",
    pr_body: str = "",
) -> list[str]:
    """
    Extract all ticket IDs from branch name, title, and body.

    Useful when a PR references multiple tickets.

    Returns:
        List of unique ticket ID strings, uppercase.
    """
    found: set[str] = set()

    for source in [branch_name, pr_title, pr_body]:
        if not source:
            continue
        for pattern in TICKET_PATTERNS:
            for match in pattern.finditer(source):
                found.add(match.group(1).upper())

    return sorted(found)
