"""
Markdown and text chunking strategies for CodeGuard.

Provides heading-based splitting for standards/ADR documents,
two-chunk ticket splitting, and single-chunk review comment packaging.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A text chunk with associated metadata."""

    text: str
    metadata: dict = field(default_factory=dict)


def _count_tokens(text: str) -> int:
    """Approximate token count via whitespace splitting."""
    return len(text.split())


def chunk_markdown_by_headings(
    text: str,
    max_tokens: int = 300,
    min_tokens: int = 30,
    source_metadata: dict | None = None,
) -> list[Chunk]:
    """
    Split Markdown text at heading boundaries (##, ###, ####).

    Strategy:
    - Split at heading lines
    - Merge consecutive small sections (< min_tokens) into one chunk
    - Split oversized sections (> max_tokens) at paragraph boundaries

    Args:
        text: Raw Markdown content.
        max_tokens: Maximum tokens per chunk (target ~100-300).
        min_tokens: Minimum tokens before a section is merged with the next.
        source_metadata: Base metadata to attach to every chunk.

    Returns:
        List of Chunk objects with text and metadata.
    """
    if not text or not text.strip():
        return []

    base_meta = source_metadata or {}
    chunks: list[Chunk] = []

    # Split on heading lines (lines starting with ## or more)
    heading_pattern = re.compile(r"^(#{2,6})\s+(.+)$", re.MULTILINE)
    sections: list[tuple[str, str]] = []  # (heading, body)

    matches = list(heading_pattern.finditer(text))

    if not matches:
        # No headings found — treat entire text as one section
        sections.append(("", text.strip()))
    else:
        # Content before first heading
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((heading, body))

    # Merge small sections and split large ones
    buffer_text = ""

    def _flush_buffer():
        nonlocal buffer_text
        if buffer_text.strip():
            chunks.append(Chunk(text=buffer_text.strip(), metadata={**base_meta}))
            buffer_text = ""

    def _split_large_text(text_to_split: str):
        """Split text that exceeds max_tokens at paragraph or word boundaries."""
        # Try paragraph boundaries first
        paragraphs = re.split(r"\n\n+", text_to_split)
        if len(paragraphs) > 1:
            para_buffer = ""
            for para in paragraphs:
                if para_buffer and _count_tokens(para_buffer + "\n\n" + para) > max_tokens:
                    chunks.append(Chunk(text=para_buffer.strip(), metadata={**base_meta}))
                    para_buffer = para
                else:
                    para_buffer = (para_buffer + "\n\n" + para).strip() if para_buffer else para
            if para_buffer.strip():
                # If still too large, do word-level split
                if _count_tokens(para_buffer) > max_tokens:
                    _split_at_words(para_buffer)
                else:
                    chunks.append(Chunk(text=para_buffer.strip(), metadata={**base_meta}))
        else:
            # Single paragraph — split at word boundaries
            _split_at_words(text_to_split)

    def _split_at_words(text_to_split: str):
        """Split a single long text block at word boundaries."""
        words = text_to_split.split()
        current = []
        for word in words:
            current.append(word)
            if len(current) >= max_tokens:
                chunks.append(Chunk(text=" ".join(current).strip(), metadata={**base_meta}))
                current = []
        if current:
            chunks.append(Chunk(text=" ".join(current).strip(), metadata={**base_meta}))

    for heading, body in sections:
        section_text = f"## {heading}\n{body}" if heading else body
        section_tokens = _count_tokens(section_text)

        if section_tokens > max_tokens:
            # This section is too large — flush buffer, then split section
            _flush_buffer()
            _split_large_text(section_text)
        elif section_tokens >= min_tokens:
            # This section is a good standalone chunk — flush buffer, start new
            _flush_buffer()
            buffer_text = section_text
        else:
            # Section is too small — try to merge with buffer
            if buffer_text:
                combined = (buffer_text + "\n\n" + section_text).strip()
                if _count_tokens(combined) <= max_tokens:
                    buffer_text = combined
                else:
                    _flush_buffer()
                    buffer_text = section_text
            else:
                buffer_text = section_text

    # Flush any remaining buffer
    _flush_buffer()

    return chunks


def chunk_ticket(
    title: str,
    description: str,
    acceptance_criteria: str = "",
    comments: str = "",
    issue_key: str = "",
    project: str = "",
    status: str = "",
    priority: str = "",
) -> list[Chunk]:
    """
    Split a ticket into two focused chunks as per the architecture spec.

    Chunk 1: Title + Description (the "what")
    Chunk 2: Acceptance Criteria + Comments (the "how" and "why")

    Returns:
        List of 1-2 Chunk objects.
    """
    base_meta = {
        "type": "ticket",
        "issue_key": issue_key,
        "project": project,
        "status": status,
        "priority": priority,
    }

    chunks: list[Chunk] = []

    # Chunk 1: Title + Description
    if title.strip():
        chunk1_text = f"# {title}\n\n{description}" if description else f"# {title}"
        chunks.append(Chunk(
            text=chunk1_text.strip(),
            metadata={**base_meta, "chunk_type": "description"},
        ))

    # Chunk 2: Acceptance Criteria + Comments
    parts = []
    if acceptance_criteria:
        parts.append(f"## Acceptance Criteria\n{acceptance_criteria}")
    if comments:
        parts.append(f"## Discussion\n{comments}")

    if parts:
        chunk2_text = "\n\n".join(parts)
        chunks.append(Chunk(
            text=chunk2_text.strip(),
            metadata={**base_meta, "chunk_type": "criteria_comments"},
        ))

    return chunks


def chunk_review_comment(
    comment_body: str,
    pr_id: int | str = "",
    author: str = "",
    repo: str = "",
    verdict: str = "",
    date: str = "",
    file_path: str = "",
) -> Chunk:
    """
    Package a single PR review comment as a chunk.

    Each review comment is stored as its own chunk with full PR metadata.
    """
    metadata = {
        "type": "review",
        "pr_id": str(pr_id),
        "author": author,
        "repo": repo,
        "verdict": verdict,
        "date": date,
    }
    if file_path:
        metadata["file_path"] = file_path

    return Chunk(text=comment_body.strip(), metadata=metadata)
