"""
Unit tests for the Markdown chunking module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codeguard.chunker import (
    Chunk,
    chunk_markdown_by_headings,
    chunk_review_comment,
    chunk_ticket,
)


class TestChunkMarkdownByHeadings:
    """Tests for heading-based Markdown splitting."""

    def test_empty_input_returns_empty(self):
        assert chunk_markdown_by_headings("") == []
        assert chunk_markdown_by_headings("   ") == []
        assert chunk_markdown_by_headings(None) == []

    def test_no_headings_returns_single_chunk(self):
        text = "This is a paragraph with no headings.\nIt has multiple lines."
        chunks = chunk_markdown_by_headings(text)
        assert len(chunks) >= 1
        assert "paragraph" in chunks[0].text

    def test_splits_at_headings(self):
        text = """## Section One

Content of section one.

## Section Two

Content of section two with more detail.

## Section Three

Content of section three.
"""
        chunks = chunk_markdown_by_headings(text, min_tokens=1)
        # Should produce multiple chunks based on headings
        assert len(chunks) >= 2
        texts = [c.text for c in chunks]
        all_text = " ".join(texts)
        assert "Section One" in all_text
        assert "Section Two" in all_text

    def test_max_tokens_enforced(self):
        # Create a section with many words
        long_para = " ".join(["word"] * 500)
        text = f"## Big Section\n\n{long_para}"
        chunks = chunk_markdown_by_headings(text, max_tokens=100, min_tokens=10)
        # Should split into multiple chunks
        assert len(chunks) > 1

    def test_metadata_carried_forward(self):
        text = "## Rules\n\nSome rules here."
        meta = {"type": "standard", "language": "python"}
        chunks = chunk_markdown_by_headings(text, source_metadata=meta)
        assert len(chunks) >= 1
        assert chunks[0].metadata["type"] == "standard"
        assert chunks[0].metadata["language"] == "python"

    def test_small_sections_merged(self):
        text = """## A

Short.

## B

Also short.

## C

Brief.
"""
        chunks = chunk_markdown_by_headings(text, max_tokens=300, min_tokens=30)
        # Very short sections should be merged
        assert len(chunks) <= 3


class TestChunkTicket:
    """Tests for the two-chunk ticket strategy."""

    def test_basic_ticket(self):
        chunks = chunk_ticket(
            title="Implement user login",
            description="Users need to be able to log in with email and password.",
            acceptance_criteria="- Email validation\n- Password hashing",
            issue_key="APP-183",
            project="mobile-app",
        )
        assert len(chunks) == 2
        assert "login" in chunks[0].text.lower()
        assert chunks[0].metadata["issue_key"] == "APP-183"
        assert chunks[0].metadata["chunk_type"] == "description"
        assert chunks[1].metadata["chunk_type"] == "criteria_comments"

    def test_ticket_without_acceptance_criteria(self):
        chunks = chunk_ticket(
            title="Fix button alignment",
            description="The submit button is misaligned on mobile.",
            issue_key="BUG-42",
        )
        assert len(chunks) == 1
        assert chunks[0].metadata["chunk_type"] == "description"

    def test_ticket_with_comments(self):
        chunks = chunk_ticket(
            title="Add search feature",
            description="Full text search needed.",
            comments="Should we use Elasticsearch? — Let's start with PostgreSQL FTS.",
            issue_key="FEAT-10",
        )
        assert len(chunks) == 2
        assert "Discussion" in chunks[1].text

    def test_empty_ticket(self):
        chunks = chunk_ticket(title="", description="")
        assert len(chunks) == 0


class TestChunkReviewComment:
    """Tests for review comment packaging."""

    def test_basic_comment(self):
        chunk = chunk_review_comment(
            comment_body="This function should handle the None case.",
            pr_id=42,
            author="alice",
            repo="api-service",
            verdict="changes_requested",
            date="2024-11-15",
        )
        assert isinstance(chunk, Chunk)
        assert "None case" in chunk.text
        assert chunk.metadata["pr_id"] == "42"
        assert chunk.metadata["verdict"] == "changes_requested"

    def test_comment_with_file_path(self):
        chunk = chunk_review_comment(
            comment_body="Use parameterised queries here.",
            pr_id=99,
            file_path="app/routes/users.py",
        )
        assert chunk.metadata["file_path"] == "app/routes/users.py"

    def test_comment_without_optional_fields(self):
        chunk = chunk_review_comment(comment_body="Looks good!")
        assert chunk.metadata["type"] == "review"
        assert chunk.metadata["pr_id"] == ""
