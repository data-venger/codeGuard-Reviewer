"""
Scorecard UI Component for CodeGuard.

Renders visual review scorecards with:
- Color-coded progress bars for each dimension
- Overall grade badge
- Merge recommendation with color
- Issue breakdown by severity
"""

import streamlit as st

from codeguard.scorecard import ReviewScorecard


def _score_color(score: int) -> str:
    """Return a hex color based on score value."""
    if score >= 80:
        return "#22c55e"  # green
    elif score >= 60:
        return "#eab308"  # yellow
    elif score >= 40:
        return "#f97316"  # orange
    return "#ef4444"  # red


def _progress_bar_html(label: str, score: int, icon: str = "") -> str:
    """Generate an HTML progress bar with color."""
    color = _score_color(score)
    return f"""
    <div style="margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-size: 0.9rem; font-weight: 600;">{icon} {label}</span>
            <span style="font-size: 0.9rem; font-weight: 700; color: {color};">{score}%</span>
        </div>
        <div style="background: rgba(255,255,255,0.1); border-radius: 8px; height: 10px; overflow: hidden;">
            <div style="width: {score}%; height: 100%; background: {color}; border-radius: 8px; 
                        transition: width 0.5s ease;"></div>
        </div>
    </div>
    """


def render_scorecard(scorecard: ReviewScorecard) -> None:
    """Render the full visual scorecard in Streamlit."""

    # ── Grade + Merge Recommendation Row ──
    col_grade, col_merge, col_issues = st.columns([1, 2, 2])

    with col_grade:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 8px;">
                <div style="font-size: 3.5rem; font-weight: 900; color: {scorecard.grade_color};
                            line-height: 1;">
                    {scorecard.grade}
                </div>
                <div style="font-size: 0.75rem; color: #888; margin-top: 4px;">
                    Overall: {scorecard.overall_score}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_merge:
        st.markdown(
            f"""
            <div style="padding: 12px 16px; border-radius: 10px; 
                        border: 2px solid {scorecard.merge_color};
                        background: {scorecard.merge_color}15;
                        text-align: center;">
                <div style="font-size: 1.5rem;">{scorecard.merge_emoji}</div>
                <div style="font-size: 0.95rem; font-weight: 700; 
                            color: {scorecard.merge_color};">
                    {scorecard.merge_label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_issues:
        critical_html = (
            f'<span style="background:#ef444430;color:#ef4444;padding:2px 8px;'
            f'border-radius:12px;font-size:0.8rem;font-weight:600;">'
            f'🔴 {scorecard.critical_count} Critical</span>'
        ) if scorecard.critical_count else ""

        major_html = (
            f'<span style="background:#f9731630;color:#f97316;padding:2px 8px;'
            f'border-radius:12px;font-size:0.8rem;font-weight:600;">'
            f'🟠 {scorecard.major_count} Major</span>'
        ) if scorecard.major_count else ""

        minor_html = (
            f'<span style="background:#eab30830;color:#eab308;padding:2px 8px;'
            f'border-radius:12px;font-size:0.8rem;font-weight:600;">'
            f'🟡 {scorecard.minor_count} Minor</span>'
        ) if scorecard.minor_count else ""

        no_issues = (
            '<span style="color:#22c55e;font-size:0.85rem;">✨ No issues found</span>'
        ) if not scorecard.issues else ""

        st.markdown(
            f"""
            <div style="padding: 12px;">
                <div style="font-size: 0.8rem; color: #888; margin-bottom: 6px;">
                    Issues Found ({len(scorecard.issues)})
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    {critical_html} {major_html} {minor_html} {no_issues}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Score Progress Bars ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(
            _progress_bar_html("Code Quality", scorecard.code_quality, "📊"),
            unsafe_allow_html=True,
        )
        st.markdown(
            _progress_bar_html("Standards Compliance", scorecard.standards_compliance, "📏"),
            unsafe_allow_html=True,
        )

    with col_right:
        st.markdown(
            _progress_bar_html("Architecture", scorecard.architecture_score, "🏛️"),
            unsafe_allow_html=True,
        )
        st.markdown(
            _progress_bar_html("Bug Safety", scorecard.bug_risk, "🛡️"),
            unsafe_allow_html=True,
        )

    # ── Issue Details (if any) ──
    if scorecard.issues:
        with st.expander(f"📋 Issue Details ({len(scorecard.issues)})", expanded=False):
            for i, issue in enumerate(scorecard.issues, 1):
                sev_icon = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(
                    issue.severity, "⚪"
                )
                st.markdown(
                    f"**{sev_icon} [{issue.severity.upper()}]** `{issue.category}` — {issue.description}"
                )
