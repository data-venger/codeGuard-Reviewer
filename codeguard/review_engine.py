"""
Review Engine for CodeGuard.

Orchestrates the full PR review loop:
1. Fetch PR metadata via GitHub API
2. Extract ticket ID from branch name
3. Multi-namespace RAG retrieval
4. Fetch PR diff (trimmed to budget)
5. Assemble prompt from template + context
6. Call LLM via Ollama, stream response
7. Return structured ReviewResult
"""

import time
from dataclasses import dataclass, field
from typing import Generator, Optional

from rich.console import Console

from codeguard.github_client import GitHubClient
from codeguard.llm_client import OllamaClient
from codeguard.retriever import Retriever, ReviewContext
from codeguard.scorecard import (
    SCORECARD_INSTRUCTION,
    ReviewScorecard,
    parse_scorecard,
    strip_scorecard_json,
)
from config.settings import settings

console = Console()

# Maximum diff tokens to include in prompt (prevent OOM on large PRs)
MAX_DIFF_TOKENS = 4000

# Prompt template as per architecture spec §6.1
SYSTEM_PROMPT = """You are a Senior Engineer at {org_name}.
You are reviewing a Pull Request. Review the code changes strictly against the provided context.
Be specific, cite line numbers when possible, and provide code examples for suggestions.
{author_guidance}"""

REVIEW_PROMPT_TEMPLATE = """## [1] Ticket Requirement
{ticket_context}

## [2] Relevant Coding Standards
{standards_context}

## [3] Architecture Decisions
{adr_context}

## [4] Similar Past Reviews
{history_context}

## [5] Code Diff
```diff
{diff}
```

## TASK
Based on the context above, provide a structured code review:

1. **Ticket Compliance**: Does the code satisfy the ticket requirements and acceptance criteria?
2. **Standards Violations**: Does the code violate any coding standards? List each violation with the specific rule.
3. **Architecture Compliance**: Does the code follow the architecture decisions (ADRs)? Flag any anti-patterns.
4. **Bugs & Edge Cases**: Are there bugs, unhandled edge cases, or security issues?
5. **Improvements**: Suggest improvements with concrete code examples.

End with a **Verdict**: one of APPROVED ✅, CHANGES_REQUESTED ⚠️, or ISSUES_FOUND ❌.

Format your response in clear Markdown with headers for each section.
{scorecard_instruction}"""


@dataclass
class ReviewResult:
    """The output of a PR review."""

    # Core output
    review_markdown: str = ""
    verdict: str = ""  # APPROVED, CHANGES_REQUESTED, ISSUES_FOUND

    # Scorecard
    scorecard: Optional[ReviewScorecard] = None

    # Metadata
    pr_number: int = 0
    pr_title: str = ""
    pr_author: str = ""
    repo: str = ""
    branch: str = ""
    ticket_id: str = ""

    # Context stats
    context: Optional[ReviewContext] = None
    model_used: str = ""
    duration_seconds: float = 0.0
    diff_tokens: int = 0
    total_context_tokens: int = 0

    @property
    def verdict_emoji(self) -> str:
        if "APPROVED" in self.verdict.upper():
            return "✅"
        elif "CHANGES" in self.verdict.upper():
            return "⚠️"
        else:
            return "❌"


def _trim_diff(diff_text: str, max_tokens: int = MAX_DIFF_TOKENS) -> str:
    """
    Trim a diff to fit within the token budget.

    Strategy: Keep the most impactful files (smallest diffs first,
    which are usually the most focused changes).
    """
    tokens = diff_text.split()
    if len(tokens) <= max_tokens:
        return diff_text

    # Truncate with a note
    trimmed = " ".join(tokens[:max_tokens])
    trimmed += "\n\n... [DIFF TRUNCATED — showing first ~{} tokens of {} total] ...".format(
        max_tokens, len(tokens)
    )
    return trimmed


def _extract_verdict(review_text: str) -> str:
    """Extract the verdict from the review output."""
    text_upper = review_text.upper()
    if "APPROVED" in text_upper and "✅" in review_text:
        return "APPROVED"
    elif "CHANGES_REQUESTED" in text_upper or "CHANGES REQUESTED" in text_upper:
        return "CHANGES_REQUESTED"
    elif "ISSUES_FOUND" in text_upper or "ISSUES FOUND" in text_upper:
        return "ISSUES_FOUND"

    # Fallback: look for verdict patterns
    if "approve" in review_text.lower() and "not" not in review_text.lower()[-50:]:
        return "APPROVED"
    return "CHANGES_REQUESTED"


class ReviewEngine:
    """Orchestrates the full PR review pipeline."""

    def __init__(
        self,
        github_client: Optional[GitHubClient] = None,
        ollama_client: Optional[OllamaClient] = None,
        retriever: Optional[Retriever] = None,
    ):
        self.github = github_client or GitHubClient()
        self.llm = ollama_client or OllamaClient()
        self.retriever = retriever or Retriever()

    def review_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        stream: bool = False,
    ) -> ReviewResult | Generator[str, None, ReviewResult]:
        """
        Execute the full review loop for a PR.

        Args:
            owner: GitHub repo owner/org.
            repo: Repository name.
            pr_number: PR number.
            stream: If True, yields tokens as they arrive and returns ReviewResult at end.

        Returns:
            ReviewResult with the complete review, or a generator if streaming.
        """
        if stream:
            return self._review_pr_streaming(owner, repo, pr_number)
        else:
            return self._review_pr_blocking(owner, repo, pr_number)

    def _review_pr_blocking(
        self, owner: str, repo: str, pr_number: int
    ) -> ReviewResult:
        """Non-streaming review — returns complete result."""
        start_time = time.time()
        result = ReviewResult(pr_number=pr_number, repo=repo)

        # Step 1: Fetch PR metadata
        console.print(f"\n[bold]🔍 Reviewing PR #{pr_number} in {owner}/{repo}...[/bold]")
        try:
            pr_data = self.github.get_pr(owner, repo, pr_number)
        except Exception as e:
            result.review_markdown = f"❌ **Failed to fetch PR:** {e}"
            return result

        result.pr_title = pr_data.get("title", "")
        result.pr_author = pr_data.get("user", {}).get("login", "")
        result.branch = pr_data.get("head", {}).get("ref", "")

        # Step 2: Fetch diff
        console.print("  Fetching diff...")
        try:
            diff_text = self.github.get_pr_diff(owner, repo, pr_number)
        except Exception as e:
            result.review_markdown = f"❌ **Failed to fetch diff:** {e}"
            return result

        trimmed_diff = _trim_diff(diff_text)
        result.diff_tokens = len(trimmed_diff.split())

        # Step 3: Multi-namespace RAG retrieval
        console.print("  Retrieving context...")
        context = self.retriever.retrieve_all(
            diff_text=diff_text,
            branch_name=result.branch,
            pr_title=result.pr_title,
            repo=repo,
            author=result.pr_author,
        )
        result.context = context
        result.ticket_id = context.ticket_id
        result.total_context_tokens = context.total_context_tokens

        # Step 4: Assemble prompt
        system_prompt = SYSTEM_PROMPT.format(
            org_name=settings.org_name,
            author_guidance=context.author_guidance,
        )

        review_prompt = REVIEW_PROMPT_TEMPLATE.format(
            ticket_context=context.ticket_context,
            standards_context=context.standards_context,
            adr_context=context.adr_context,
            history_context=context.history_context,
            diff=trimmed_diff,
            scorecard_instruction=SCORECARD_INSTRUCTION,
        )

        # Step 5: Call LLM
        console.print("  Generating review...")
        result.model_used = self.llm.model
        review_text = self.llm.generate(
            prompt=review_prompt,
            system_prompt=system_prompt,
            stream=False,
        )

        # Parse scorecard from review
        result.scorecard = parse_scorecard(review_text)
        result.review_markdown = strip_scorecard_json(review_text)
        result.verdict = _extract_verdict(review_text)
        result.duration_seconds = time.time() - start_time

        # Store review in Qdrant history
        self._store_review(result)

        console.print(f"  [green]✓ Review complete in {result.duration_seconds:.1f}s[/green]")
        return result

    def _review_pr_streaming(
        self, owner: str, repo: str, pr_number: int
    ) -> Generator[str, None, ReviewResult]:
        """Streaming review — yields tokens as they arrive."""
        start_time = time.time()
        result = ReviewResult(pr_number=pr_number, repo=repo)

        # Step 1: Fetch PR metadata
        try:
            pr_data = self.github.get_pr(owner, repo, pr_number)
        except Exception as e:
            result.review_markdown = f"❌ **Failed to fetch PR:** {e}"
            yield result.review_markdown
            return result

        result.pr_title = pr_data.get("title", "")
        result.pr_author = pr_data.get("user", {}).get("login", "")
        result.branch = pr_data.get("head", {}).get("ref", "")

        # Step 2: Fetch diff
        try:
            diff_text = self.github.get_pr_diff(owner, repo, pr_number)
        except Exception as e:
            result.review_markdown = f"❌ **Failed to fetch diff:** {e}"
            yield result.review_markdown
            return result

        trimmed_diff = _trim_diff(diff_text)
        result.diff_tokens = len(trimmed_diff.split())

        # Step 3: RAG retrieval
        context = self.retriever.retrieve_all(
            diff_text=diff_text,
            branch_name=result.branch,
            pr_title=result.pr_title,
            repo=repo,
            author=result.pr_author,
        )
        result.context = context
        result.ticket_id = context.ticket_id
        result.total_context_tokens = context.total_context_tokens

        # Step 4: Assemble prompt
        system_prompt = SYSTEM_PROMPT.format(
            org_name=settings.org_name,
            author_guidance=context.author_guidance,
        )

        review_prompt = REVIEW_PROMPT_TEMPLATE.format(
            ticket_context=context.ticket_context,
            standards_context=context.standards_context,
            adr_context=context.adr_context,
            history_context=context.history_context,
            diff=trimmed_diff,
            scorecard_instruction=SCORECARD_INSTRUCTION,
        )

        # Step 5: Stream LLM response
        result.model_used = self.llm.model
        full_response = []

        for token in self.llm.generate(
            prompt=review_prompt,
            system_prompt=system_prompt,
            stream=True,
        ):
            full_response.append(token)
            yield token

        raw_text = "".join(full_response)
        result.scorecard = parse_scorecard(raw_text)
        result.review_markdown = strip_scorecard_json(raw_text)
        result.verdict = _extract_verdict(raw_text)
        result.duration_seconds = time.time() - start_time

        # Store review in Qdrant history
        self._store_review(result)

        return result

    def _store_review(self, result: ReviewResult) -> None:
        """Store completed review in Qdrant history collection for future reference."""
        try:
            from codeguard.embeddings import EmbeddingEngine
            from codeguard.qdrant_store import QdrantManager

            embedder = EmbeddingEngine()
            qdrant = QdrantManager()

            # Build a summary text for embedding
            summary = (
                f"PR #{result.pr_number} in {result.repo}: {result.pr_title}\n"
                f"Author: {result.pr_author} | Branch: {result.branch}\n"
                f"Verdict: {result.verdict}\n"
                f"{result.review_markdown[:1000]}"
            )

            vectors = embedder.embed([summary])

            metadata = {
                "type": "review",
                "pr_number": result.pr_number,
                "repo": result.repo,
                "pr_title": result.pr_title,
                "author": result.pr_author,
                "verdict": result.verdict,
                "model": result.model_used,
            }

            if result.scorecard:
                metadata["code_quality"] = result.scorecard.code_quality
                metadata["standards_compliance"] = result.scorecard.standards_compliance
                metadata["merge_recommendation"] = result.scorecard.merge_recommendation

            qdrant.upsert_points(
                collection_name="history",
                texts=[summary],
                vectors=vectors,
                metadata=[metadata],
            )
            console.print("  [dim]📦 Review stored in history collection[/dim]")

        except Exception as e:
            console.print(f"  [yellow]⚠ Failed to store review: {e}[/yellow]")
