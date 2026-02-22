"""
Streamlit UI Components for CodeGuard.

Reusable rendering functions for PR cards, reviews, verdicts, and context debug panels.
"""

import streamlit as st


def render_pr_card(pr: dict) -> None:
    """Render a PR summary card in the Streamlit UI."""
    number = pr.get("number", "?")
    title = pr.get("title", "Untitled")
    author = pr.get("user", {}).get("login", "unknown")
    branch = pr.get("head", {}).get("ref", "")
    state = pr.get("state", "")
    created = pr.get("created_at", "")[:10]
    labels = [l.get("name", "") for l in pr.get("labels", [])]
    additions = pr.get("additions", 0)
    deletions = pr.get("deletions", 0)
    changed_files = pr.get("changed_files", 0)

    label_badges = " ".join([f"`{l}`" for l in labels]) if labels else ""

    st.markdown(
        f"""
**#{number}** — {title}

👤 `{author}` · 🌿 `{branch}` · 📅 {created} {label_badges}

`+{additions}` / `-{deletions}` across **{changed_files}** files
        """,
        unsafe_allow_html=True,
    )


def render_verdict_badge(verdict: str) -> None:
    """Render a coloured verdict badge."""
    if "APPROVED" in verdict.upper():
        st.success("✅ **APPROVED** — No critical issues found")
    elif "CHANGES" in verdict.upper():
        st.warning("⚠️ **CHANGES REQUESTED** — Issues require attention")
    else:
        st.error("❌ **ISSUES FOUND** — Critical problems detected")


def render_review(review_markdown: str, verdict: str = "") -> None:
    """Render the full review output with verdict badge and markdown."""
    if verdict:
        render_verdict_badge(verdict)
        st.divider()

    st.markdown(review_markdown)


def render_review_metadata(
    model: str = "",
    duration: float = 0.0,
    diff_tokens: int = 0,
    context_tokens: int = 0,
    ticket_id: str = "",
) -> None:
    """Render review metadata in a compact metrics row."""
    cols = st.columns(5)
    with cols[0]:
        st.metric("🤖 Model", model.split(":")[0] if model else "N/A")
    with cols[1]:
        st.metric("⏱️ Duration", f"{duration:.1f}s" if duration else "N/A")
    with cols[2]:
        st.metric("📄 Diff Tokens", f"{diff_tokens:,}" if diff_tokens else "N/A")
    with cols[3]:
        st.metric("📚 Context", f"{context_tokens:,}" if context_tokens else "N/A")
    with cols[4]:
        st.metric("🎫 Ticket", ticket_id if ticket_id else "N/A")


def render_context_debug(context) -> None:
    """Render expandable panels showing retrieved context for each layer."""
    if not context:
        return

    st.subheader("🔍 Retrieved Context")

    with st.expander("🎫 Ticket Context", expanded=False):
        if context.ticket_context:
            st.markdown(context.ticket_context)
        else:
            st.caption("No ticket context retrieved.")

    with st.expander("📏 Coding Standards", expanded=False):
        st.caption(f"Matched: {context.matched_standards_count} chunks")
        if context.standards_context:
            st.markdown(context.standards_context)
        else:
            st.caption("No standards matched.")

    with st.expander("🏛️ Architecture Decisions (ADRs)", expanded=False):
        st.caption(f"Matched: {context.matched_adr_count} chunks")
        if context.adr_context:
            st.markdown(context.adr_context)
        else:
            st.caption("No ADRs matched.")

    with st.expander("📜 Historical Reviews", expanded=False):
        st.caption(f"Matched: {context.matched_history_count} chunks")
        if context.history_context:
            st.markdown(context.history_context)
        else:
            st.caption("No historical reviews matched.")

    with st.expander("💻 Codebase Context", expanded=False):
        st.caption(f"Matched: {context.matched_codebase_count} chunks")
        if context.codebase_context:
            st.markdown(context.codebase_context)
        else:
            st.caption("No codebase context matched.")

    if context.author_guidance:
        with st.expander("👤 Author Context", expanded=False):
            st.info(context.author_guidance)
