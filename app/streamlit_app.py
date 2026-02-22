"""
CodeGuard — Streamlit PR Review Dashboard

The main application entry point. Provides:
- Sidebar: org/repo configuration, Ollama health status
- PR Browser: list open PRs, select one for review
- Review Panel: streaming AI review output with verdict and context debug

Launch with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.components import (
    render_context_debug,
    render_pr_card,
    render_review,
    render_review_metadata,
    render_verdict_badge,
)
from app.chat_tab import render_chat
from app.scorecard_ui import render_scorecard
from codeguard.github_client import GitHubClient
from codeguard.llm_client import OllamaClient
from codeguard.review_engine import ReviewEngine
from config.settings import settings

# ── Page Config ──
st.set_page_config(
    page_title="CodeGuard — AI PR Reviewer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
    /* Dark theme enhancements */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .review-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2rem;
        font-weight: 800;
    }
    .pr-card {
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: rgba(255,255,255,0.03);
    }
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-healthy { background: #22c55e22; color: #22c55e; }
    .status-unhealthy { background: #ef444422; color: #ef4444; }
</style>
""", unsafe_allow_html=True)


# ── Session State Init ──
if "selected_pr" not in st.session_state:
    st.session_state.selected_pr = None
if "review_result" not in st.session_state:
    st.session_state.review_result = None
if "prs" not in st.session_state:
    st.session_state.prs = []


# ── Sidebar ──
with st.sidebar:
    st.markdown("# 🛡️ CodeGuard")
    st.caption("RAG-Based PR Reviewer")
    st.divider()

    # GitHub Configuration
    st.subheader("⚙️ Configuration")

    github_org = st.text_input(
        "GitHub Org / Owner",
        value=settings.github_org,
        help="GitHub organisation or username",
    )

    github_repo = st.text_input(
        "Repository",
        value=settings.github_repos_list[0] if settings.github_repos_list else "",
        help="Repository name to review PRs from",
    )

    st.divider()

    # System Health
    st.subheader("🏥 System Health")

    # Ollama status
    ollama = OllamaClient()
    ollama_healthy = ollama.is_healthy()
    if ollama_healthy:
        st.markdown(
            '<span class="status-badge status-healthy">● Ollama Online</span>',
            unsafe_allow_html=True,
        )
        models = ollama.list_models()
        st.caption(f"Models: {', '.join(models[:3])}")
    else:
        st.markdown(
            '<span class="status-badge status-unhealthy">● Ollama Offline</span>',
            unsafe_allow_html=True,
        )
        st.caption("Run: `ollama serve`")

    # Qdrant status
    try:
        from codeguard.qdrant_store import qdrant_manager
        info = qdrant_manager.client.get_collections()
        collection_count = len(info.collections)
        st.markdown(
            '<span class="status-badge status-healthy">● Qdrant Online</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Collections: {collection_count}")
    except Exception:
        st.markdown(
            '<span class="status-badge status-unhealthy">● Qdrant Offline</span>',
            unsafe_allow_html=True,
        )
        st.caption("Run: `docker compose up -d`")

    st.divider()

    # Model selection
    st.subheader("🤖 Model")
    model_name = st.text_input(
        "Ollama Model",
        value="qwen2.5-coder:7b-instruct-q4_K_M",
        help="Model name as registered in Ollama",
    )

    st.divider()
    st.caption("CodeGuard v0.1.0 · Local-First AI Reviews")


# ── Main Content ──
st.markdown('<h1 class="review-header">Pull Request Review</h1>', unsafe_allow_html=True)
st.caption(f"Repository: **{github_org}/{github_repo}**" if github_org and github_repo else "Configure a repository in the sidebar →")

# ── PR Browser Tab / Review Tab / Chat Tab ──
tab_browse, tab_review, tab_chat = st.tabs(["📋 Browse PRs", "🔍 Review", "💬 Chat"])

with tab_browse:
    if not github_org or not github_repo:
        st.info("👈 Enter a GitHub org and repository in the sidebar to get started.")
    else:
        col_refresh, col_spacer = st.columns([1, 5])
        with col_refresh:
            refresh = st.button("🔄 Refresh PRs", use_container_width=True)

        if refresh or not st.session_state.prs:
            with st.spinner("Fetching open PRs..."):
                try:
                    client = GitHubClient()
                    prs = client.list_open_prs(github_org, github_repo)
                    st.session_state.prs = prs
                except Exception as e:
                    st.error(f"Failed to fetch PRs: {e}")
                    st.session_state.prs = []

        prs = st.session_state.prs

        if prs:
            st.success(f"Found **{len(prs)}** open pull requests")

            for pr in prs:
                with st.container():
                    col_info, col_action = st.columns([5, 1])

                    with col_info:
                        render_pr_card(pr)

                    with col_action:
                        if st.button(
                            "🔍 Review",
                            key=f"review_{pr['number']}",
                            use_container_width=True,
                        ):
                            st.session_state.selected_pr = pr
                            st.session_state.review_result = None
                            st.rerun()

                    st.divider()
        elif st.session_state.prs is not None:
            st.info("No open PRs found in this repository.")


with tab_review:
    pr = st.session_state.selected_pr

    if not pr:
        st.info("👈 Select a PR from the Browse tab to start a review.")
    else:
        pr_number = pr.get("number", 0)
        pr_title = pr.get("title", "")
        pr_author = pr.get("user", {}).get("login", "")
        branch = pr.get("head", {}).get("ref", "")

        st.subheader(f"PR #{pr_number}: {pr_title}")
        st.caption(f"👤 {pr_author} · 🌿 `{branch}`")
        st.divider()

        # Review button
        if st.session_state.review_result is None:
            col_start, col_back = st.columns([1, 5])
            with col_start:
                start_review = st.button(
                    "🚀 Start Review",
                    type="primary",
                    use_container_width=True,
                )
            with col_back:
                if st.button("← Back to PR list"):
                    st.session_state.selected_pr = None
                    st.rerun()

            if start_review:
                if not ollama_healthy:
                    st.error("❌ Ollama is not running. Start it with: `ollama serve`")
                else:
                    # Run the review with streaming
                    engine = ReviewEngine(
                        ollama_client=OllamaClient(model=model_name),
                    )

                    # Show progress stages
                    status_container = st.empty()
                    review_container = st.empty()

                    with status_container.status("🔍 Reviewing PR...", expanded=True) as status:
                        st.write("📥 Fetching PR metadata and diff...")

                        try:
                            # Use blocking mode for simpler Streamlit integration
                            result = engine.review_pr(
                                owner=github_org,
                                repo=github_repo,
                                pr_number=pr_number,
                                stream=False,
                            )

                            st.write("✅ Review complete!")
                            status.update(label="✅ Review complete!", state="complete")

                            st.session_state.review_result = result
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Review failed: {e}")
                            status.update(label="❌ Review failed", state="error")
        else:
            # Display the completed review
            result = st.session_state.review_result

            # Metadata row
            render_review_metadata(
                model=result.model_used,
                duration=result.duration_seconds,
                diff_tokens=result.diff_tokens,
                context_tokens=result.total_context_tokens,
                ticket_id=result.ticket_id,
            )

            st.divider()

            # Scorecard (Phase 4)
            if result.scorecard:
                st.subheader("📊 Review Scorecard")
                render_scorecard(result.scorecard)
                st.divider()

            # Verdict + Review
            render_review(result.review_markdown, result.verdict)

            st.divider()

            # Context debug section
            render_context_debug(result.context)

            st.divider()

            # Action buttons
            col_new, col_back2, col_spacer2 = st.columns([1, 1, 4])
            with col_new:
                if st.button("🔄 Re-review", use_container_width=True):
                    st.session_state.review_result = None
                    st.rerun()
            with col_back2:
                if st.button("← Back to PRs", use_container_width=True):
                    st.session_state.selected_pr = None
                    st.session_state.review_result = None
                    st.rerun()


with tab_chat:
    render_chat(model_name=model_name)
