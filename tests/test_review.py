"""
Tests for ticket ID extraction and review engine components.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codeguard.ticket_extractor import extract_all_ticket_ids, extract_ticket_id


class TestTicketExtractor:
    """Tests for ticket ID regex extraction."""

    def test_branch_with_ticket_id(self):
        assert extract_ticket_id("feature/APP-183-add-login") == "APP-183"

    def test_branch_feat_prefix(self):
        assert extract_ticket_id("feat/FEAT-42-search") == "FEAT-42"

    def test_branch_bugfix_prefix(self):
        assert extract_ticket_id("bugfix/BUG-7-fix-crash") == "BUG-7"

    def test_pr_title_with_brackets(self):
        assert extract_ticket_id("", "[APP-183] Add user login") == "APP-183"

    def test_pr_title_with_colon(self):
        assert extract_ticket_id("", "FEAT-42: Implement search") == "FEAT-42"

    def test_branch_preferred_over_title(self):
        result = extract_ticket_id("feature/APP-100-stuff", "[FEAT-200] Other title")
        assert result == "APP-100"

    def test_no_ticket_id(self):
        assert extract_ticket_id("main") is None
        assert extract_ticket_id("", "Fix typo in readme") is None

    def test_empty_inputs(self):
        assert extract_ticket_id("", "") is None

    def test_lowercase_branch(self):
        result = extract_ticket_id("feature/app-123-something")
        assert result == "APP-123"

    def test_extract_all_from_body(self):
        ids = extract_all_ticket_ids(
            branch_name="feature/APP-100-main",
            pr_title="Implement APP-100",
            pr_body="This also fixes BUG-42 and relates to FEAT-10.",
        )
        assert "APP-100" in ids
        assert "BUG-42" in ids
        assert "FEAT-10" in ids


class TestDiffTrimming:
    """Tests for diff trimming logic."""

    def test_short_diff_unchanged(self):
        from codeguard.review_engine import _trim_diff
        diff = "short diff content"
        assert _trim_diff(diff) == diff

    def test_long_diff_trimmed(self):
        from codeguard.review_engine import _trim_diff
        long_diff = " ".join(["word"] * 10000)
        result = _trim_diff(long_diff, max_tokens=100)
        assert len(result.split()) < 200  # trimmed + note
        assert "TRUNCATED" in result

    def test_exact_budget_unchanged(self):
        from codeguard.review_engine import _trim_diff
        diff = " ".join(["word"] * 4000)
        result = _trim_diff(diff, max_tokens=4000)
        assert "TRUNCATED" not in result


class TestVerdictExtraction:
    """Tests for verdict parsing from review output."""

    def test_approved(self):
        from codeguard.review_engine import _extract_verdict
        assert _extract_verdict("**Verdict**: APPROVED ✅") == "APPROVED"

    def test_changes_requested(self):
        from codeguard.review_engine import _extract_verdict
        assert _extract_verdict("**Verdict**: CHANGES_REQUESTED ⚠️") == "CHANGES_REQUESTED"

    def test_issues_found(self):
        from codeguard.review_engine import _extract_verdict
        assert _extract_verdict("**Verdict**: ISSUES_FOUND ❌") == "ISSUES_FOUND"
