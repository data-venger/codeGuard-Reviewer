"""
Streamlit Chat Tab for CodeGuard Agent.

Provides a conversational chat interface where users can ask
natural language questions and the agent routes to the appropriate tools.
"""

import streamlit as st

from codeguard.agent.agent import run_agent_query
from langchain_core.messages import AIMessage, HumanMessage


def render_chat(model_name: str = "qwen2.5-coder:7b-instruct-q4_K_M"):
    """Render the chat tab with message history and agent interaction."""

    # Init session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_lc_history" not in st.session_state:
        st.session_state.chat_lc_history = []

    # Header
    st.subheader("💬 Ask CodeGuard")
    st.caption(
        "Ask anything — list PRs, review code, query standards, search past reviews, "
        "or look up architecture decisions."
    )

    # Example queries
    with st.expander("💡 Example queries", expanded=False):
        examples = [
            "Show me the open PRs",
            "Review PR #5",
            "What are our Python naming conventions?",
            "Were there past reviews about error handling?",
            "What ADRs exist for the repository pattern?",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(f"📝 {ex}", key=f"example_{i}", use_container_width=True):
                    st.session_state.pending_query = ex
                    st.rerun()

    st.divider()

    # Display chat history
    for msg in st.session_state.chat_messages:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])

            # Show tool calls if any
            if role == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    with st.expander(
                        f"🔧 Used tool: `{tc['name']}`", expanded=False
                    ):
                        st.code(str(tc.get("args", {})), language="json")

    # Chat input
    prompt = st.chat_input("Ask CodeGuard anything...")

    # Check for pending query from example buttons
    if not prompt and "pending_query" in st.session_state:
        prompt = st.session_state.pending_query
        del st.session_state.pending_query

    if prompt:
        # Display user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt,
        })
        with st.chat_message("user"):
            st.markdown(prompt)

        # Run agent
        with st.chat_message("assistant"):
            with st.status("🤔 Thinking...", expanded=True) as status:
                st.write("Processing your question...")

                try:
                    result = run_agent_query(
                        query=prompt,
                        chat_history=st.session_state.chat_lc_history,
                        model=model_name,
                    )

                    # Show tool calls
                    if result["tool_calls"]:
                        for tc in result["tool_calls"]:
                            st.write(f"🔧 Called: `{tc['name']}`")

                    status.update(label="✅ Done!", state="complete")

                except Exception as e:
                    result = {
                        "response": f"❌ Error: {e}",
                        "tool_calls": [],
                        "tool_results": [],
                    }
                    status.update(label="❌ Error", state="error")

            # Display response
            st.markdown(result["response"])

            # Show tool details
            if result["tool_calls"]:
                for i, tc in enumerate(result["tool_calls"]):
                    with st.expander(
                        f"🔧 Tool: `{tc['name']}`", expanded=False
                    ):
                        st.code(str(tc.get("args", {})), language="json")
                        if i < len(result["tool_results"]):
                            tr = result["tool_results"][i]
                            st.markdown(tr.get("result", "")[:2000])

        # Save to history
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": result["response"],
            "tool_calls": result["tool_calls"],
        })

        # Update LangChain history for context
        st.session_state.chat_lc_history.append(
            HumanMessage(content=prompt)
        )
        st.session_state.chat_lc_history.append(
            AIMessage(content=result["response"])
        )

        # Keep history manageable (last 10 turns)
        if len(st.session_state.chat_lc_history) > 20:
            st.session_state.chat_lc_history = (
                st.session_state.chat_lc_history[-20:]
            )

    # Clear chat button
    if st.session_state.chat_messages:
        st.divider()
        if st.button("🗑️ Clear chat", use_container_width=False):
            st.session_state.chat_messages = []
            st.session_state.chat_lc_history = []
            st.rerun()
