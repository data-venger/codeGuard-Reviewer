"""
Scorecard Engine for CodeGuard.

Parses structured scores from LLM review output and provides
a ReviewScorecard with code quality %, standards compliance %,
architecture score, bug risk, merge recommendation, and issue breakdown.
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str = ""  # "critical", "major", "minor"
    category: str = ""  # "standards", "architecture", "bug", "improvement"
    description: str = ""


@dataclass
class ReviewScorecard:
    """Structured scoring for a PR review."""

    # Scores (0–100)
    code_quality: int = 0
    standards_compliance: int = 0
    architecture_score: int = 0
    bug_risk: int = 0  # Higher = safer (100 = no bugs)

    # Merge decision
    merge_recommendation: str = "IMPROVE"  # "MERGE", "IMPROVE", "BLOCK"

    # Issues
    issues: list[ReviewIssue] = field(default_factory=list)

    @property
    def overall_score(self) -> int:
        """Weighted average across all dimensions."""
        return int(
            self.code_quality * 0.30
            + self.standards_compliance * 0.25
            + self.architecture_score * 0.20
            + self.bug_risk * 0.25
        )

    @property
    def grade(self) -> str:
        """Letter grade based on overall score."""
        s = self.overall_score
        if s >= 90:
            return "A"
        elif s >= 80:
            return "B"
        elif s >= 70:
            return "C"
        elif s >= 60:
            return "D"
        return "F"

    @property
    def grade_color(self) -> str:
        """Color for the grade."""
        g = self.grade
        if g == "A":
            return "#22c55e"  # green
        elif g == "B":
            return "#84cc16"  # lime
        elif g == "C":
            return "#eab308"  # yellow
        elif g == "D":
            return "#f97316"  # orange
        return "#ef4444"  # red

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "major")

    @property
    def minor_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "minor")

    @property
    def merge_color(self) -> str:
        if self.merge_recommendation == "MERGE":
            return "#22c55e"
        elif self.merge_recommendation == "IMPROVE":
            return "#eab308"
        return "#ef4444"

    @property
    def merge_emoji(self) -> str:
        if self.merge_recommendation == "MERGE":
            return "✅"
        elif self.merge_recommendation == "IMPROVE":
            return "⚠️"
        return "❌"

    @property
    def merge_label(self) -> str:
        if self.merge_recommendation == "MERGE":
            return "Ready to Merge"
        elif self.merge_recommendation == "IMPROVE":
            return "Needs Improvement"
        return "Block — Critical Issues"


# The JSON block the LLM should output at the end of its review
SCORECARD_INSTRUCTION = """

After your review, output a JSON scorecard block wrapped in ```json tags with EXACTLY this structure:
```json
{
  "code_quality": <0-100>,
  "standards_compliance": <0-100>,
  "architecture_score": <0-100>,
  "bug_risk": <0-100>,
  "merge_recommendation": "<MERGE|IMPROVE|BLOCK>",
  "issues": [
    {"severity": "<critical|major|minor>", "category": "<standards|architecture|bug|improvement>", "description": "<brief description>"}
  ]
}
```

Scoring guidelines:
- **code_quality**: Overall code quality. 90+ = excellent, 70-89 = good, 50-69 = needs work, <50 = poor
- **standards_compliance**: % of coding standards followed. 100 = fully compliant  
- **architecture_score**: ADR compliance. 100 = follows all patterns
- **bug_risk**: Safety score (100 = no bugs found, 0 = critical bugs everywhere)
- **merge_recommendation**: MERGE if scores are all 70+, IMPROVE if any 50-69, BLOCK if any <50 or critical bugs"""


def parse_scorecard(review_text: str) -> ReviewScorecard:
    """
    Extract a ReviewScorecard from LLM review text.

    Looks for a JSON block in the review. Falls back to heuristic
    scoring if no JSON is found.
    """
    scorecard = ReviewScorecard()

    # Try extracting JSON block
    json_match = re.search(
        r"```json\s*\n?\s*(\{.*?\})\s*\n?\s*```",
        review_text,
        re.DOTALL,
    )

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            scorecard.code_quality = _clamp(data.get("code_quality", 70))
            scorecard.standards_compliance = _clamp(
                data.get("standards_compliance", 70)
            )
            scorecard.architecture_score = _clamp(
                data.get("architecture_score", 70)
            )
            scorecard.bug_risk = _clamp(data.get("bug_risk", 70))

            rec = data.get("merge_recommendation", "IMPROVE").upper()
            if rec in ("MERGE", "IMPROVE", "BLOCK"):
                scorecard.merge_recommendation = rec
            else:
                scorecard.merge_recommendation = "IMPROVE"

            for issue in data.get("issues", []):
                scorecard.issues.append(
                    ReviewIssue(
                        severity=issue.get("severity", "minor"),
                        category=issue.get("category", "improvement"),
                        description=issue.get("description", ""),
                    )
                )
            return scorecard

        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # Fall through to heuristic

    # Heuristic fallback based on verdict keywords
    return _heuristic_scorecard(review_text)


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    """Clamp a value between low and high."""
    try:
        return max(low, min(high, int(value)))
    except (ValueError, TypeError):
        return 70


def _heuristic_scorecard(review_text: str) -> ReviewScorecard:
    """
    Generate approximate scores from review text when no JSON is present.
    Uses keyword analysis to estimate scores.
    """
    text_lower = review_text.lower()
    scorecard = ReviewScorecard()

    # Count severity indicators
    critical_words = len(re.findall(
        r"\b(critical|severe|security\s*vuln|sql\s*injection|xss|rce)\b",
        text_lower,
    ))
    major_words = len(re.findall(
        r"\b(major|significant|important|missing|error|bug|violation)\b",
        text_lower,
    ))
    minor_words = len(re.findall(
        r"\b(minor|trivial|suggestion|consider|could|nit|style)\b",
        text_lower,
    ))
    positive_words = len(re.findall(
        r"\b(good|excellent|clean|well|correct|proper|follow|compliant)\b",
        text_lower,
    ))

    # Verdict-based baseline
    if "approved" in text_lower and "✅" in review_text:
        baseline = 85
    elif "changes_requested" in text_lower or "changes requested" in text_lower:
        baseline = 65
    elif "issues_found" in text_lower or "issues found" in text_lower:
        baseline = 45
    else:
        baseline = 70

    # Adjust based on keyword density
    penalty = critical_words * 15 + major_words * 5 + minor_words * 2
    bonus = positive_words * 3

    scorecard.code_quality = _clamp(baseline - penalty + bonus)
    scorecard.standards_compliance = _clamp(baseline - major_words * 8 + bonus)
    scorecard.architecture_score = _clamp(baseline - critical_words * 10 + bonus)
    scorecard.bug_risk = _clamp(baseline - critical_words * 20 - major_words * 5 + bonus)

    # Merge recommendation
    if scorecard.code_quality >= 70 and scorecard.bug_risk >= 70:
        scorecard.merge_recommendation = "MERGE"
    elif critical_words > 0 or scorecard.code_quality < 50:
        scorecard.merge_recommendation = "BLOCK"
    else:
        scorecard.merge_recommendation = "IMPROVE"

    # Create issues from keyword matches
    if critical_words > 0:
        scorecard.issues.append(ReviewIssue(
            severity="critical",
            category="bug",
            description="Critical issues detected in review",
        ))
    if major_words > 0:
        scorecard.issues.append(ReviewIssue(
            severity="major",
            category="standards",
            description=f"{major_words} major issue(s) identified",
        ))
    if minor_words > 0:
        scorecard.issues.append(ReviewIssue(
            severity="minor",
            category="improvement",
            description=f"{minor_words} minor suggestion(s)",
        ))

    return scorecard


def strip_scorecard_json(review_text: str) -> str:
    """Remove the JSON scorecard block from the review text for clean display."""
    return re.sub(
        r"\n*```json\s*\n?\s*\{[^}]*\"merge_recommendation\"[^}]*\}.*?```\s*",
        "",
        review_text,
        flags=re.DOTALL,
    ).strip()
