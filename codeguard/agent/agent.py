"""
LangChain Agent for CodeGuard.

Uses a two-stage approach for reliable tool routing with local models:
1. Intent detection: classify user query → tool name
2. Tool execution: run the matched tool
3. Response synthesis: format the result nicely

This avoids relying on structured tool-calling (which smaller models
handle poorly), using keyword/intent matching instead.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from codeguard.agent.prompts import SYSTEM_PROMPT
from codeguard.agent.tools import (
    ALL_TOOLS,
    list_open_prs,
    review_pr,
    search_adrs,
    search_history,
    search_standards,
)
from config.settings import settings


# ── Intent patterns for reliable local routing ──

INTENT_PATTERNS = [
    {
        "name": "list_open_prs",
        "patterns": [
            r"\b(list|show|get|fetch|open)\b.*\b(pr|pull\s*request|prs|pull\s*requests)\b",
            r"\bpr\s*list\b",
            r"\bopen\s*pr\b",
            r"\bwhat\s*(are|is).*\bpr\b",
        ],
        "tool": list_open_prs,
    },
    {
        "name": "review_pr",
        "patterns": [
            r"\breview\b.*\b(?:pr|pull\s*request)\s*#?\s*(\d+)\b",
            r"\b(?:pr|pull\s*request)\s*#?\s*(\d+)\b.*\breview\b",
            r"\bcheck\b.*\b(?:pr|pull\s*request)\s*#?\s*(\d+)\b",
            r"\banalyze\b.*\b(?:pr|pull\s*request)\s*#?\s*(\d+)\b",
        ],
        "tool": review_pr,
        "extract_pr_number": True,
    },
    {
        "name": "search_standards",
        "patterns": [
            r"\b(standard|convention|rule|guideline|best\s*practice|coding\s*standard|naming)\b",
            r"\b(how\s*should|what\s*are\s*our|what\s*is\s*the)\b.*\b(rule|convention|standard|practice)\b",
            r"\bstyle\s*guide\b",
        ],
        "tool": search_standards,
    },
    {
        "name": "search_adrs",
        "patterns": [
            r"\badr\b",
            r"\barchitect",
            r"\bdesign\s*(decision|pattern|record)\b",
            r"\b(pattern|architecture)\b.*\b(decision|record)\b",
            r"\brepository\s*pattern\b",
            r"\bdecision\s*record\b",
        ],
        "tool": search_adrs,
    },
    {
        "name": "search_history",
        "patterns": [
            r"\b(past|previous|historical|old|earlier)\b.*\breview",
            r"\breview.*\b(history|past|before)\b",
            r"\bhistory\b",
            r"\bwhat\s*(was|were)\b.*\b(flagged|reviewed|commented)\b",
            r"\bwere\s+there\b.*\breview",
            r"\bprevious\b.*\b(bug|issue|problem|error)\b",
            r"\breview.*\b(about|regarding|on|for)\b",
        ],
        "tool": search_history,
    },
]


def _detect_intent(query: str) -> dict | None:
    """Detect which tool to use based on the query text."""
    query_lower = query.lower()

    for intent in INTENT_PATTERNS:
        for pattern in intent["patterns"]:
            if re.search(pattern, query_lower):
                return intent

    return None


def _extract_pr_number(query: str) -> int | None:
    """Extract a PR number from a query string."""
    match = re.search(r"#?\s*(\d+)", query)
    if match:
        return int(match.group(1))
    return None


def _extract_search_query(query: str) -> str:
    """Extract the core search topic from a user question."""
    # Remove common question patterns to get the search term
    cleaned = re.sub(
        r"^(what|how|show|tell|find|search|list|get|are|is|our|the|me|about)\s+",
        "",
        query.lower(),
    )
    cleaned = re.sub(
        r"\b(standards?|conventions?|rules?|guidelines?|adrs?|reviews?|prs?|"
        r"coding|past|previous|history|historical)\b",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # If we cleaned too aggressively, use the original
    return cleaned if len(cleaned) > 3 else query


def create_agent(
    model: str = "",
    temperature: float = 0.1,
):
    """
    Create a chat LLM instance for response synthesis.

    Auto-detects provider: uses ChatGroq if GROQ_API_KEY is set,
    otherwise falls back to ChatOllama.
    """
    provider = settings.llm_provider.lower()

    if provider == "groq" or (settings.groq_api_key and provider != "ollama"):
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model or settings.groq_model,
            temperature=temperature,
            api_key=settings.groq_api_key,
        )
    else:
        return ChatOllama(
            model=model or "qwen2.5-coder:7b-instruct-q4_K_M",
            temperature=temperature,
            num_ctx=8192,
        )


def run_agent_query(
    query: str,
    chat_history: list | None = None,
    model: str = "",
) -> dict:
    """
    Run a query through intent-based routing and tool execution.

    Flow:
    1. Detect intent from query → map to tool
    2. Execute the tool with extracted parameters
    3. Use LLM to synthesise a natural response from tool output

    Returns:
        dict with "response", "tool_calls", "tool_results"
    """
    tool_calls_made = []
    tool_results = []

    # Step 1: Detect intent
    intent = _detect_intent(query)

    if intent:
        tool_name = intent["name"]
        tool_fn = intent["tool"]

        # Step 2: Extract parameters and execute tool
        try:
            if tool_name == "review_pr":
                pr_number = _extract_pr_number(query)
                if pr_number:
                    tool_args = {"pr_number": pr_number}
                    tool_calls_made.append({"name": tool_name, "args": tool_args})
                    result = tool_fn.invoke(tool_args)
                else:
                    result = "⚠️ I couldn't find a PR number in your question. Please specify like 'Review PR #5'."
                    tool_calls_made.append({"name": tool_name, "args": {"query": query}})

            elif tool_name == "list_open_prs":
                tool_args = {}
                tool_calls_made.append({"name": tool_name, "args": tool_args})
                result = tool_fn.invoke(tool_args)

            elif tool_name in ("search_standards", "search_history", "search_adrs"):
                search_query = _extract_search_query(query)
                # Use the original query if extraction produced nothing useful
                if len(search_query) < 3:
                    search_query = query
                tool_args = {"query": search_query}
                tool_calls_made.append({"name": tool_name, "args": tool_args})
                result = tool_fn.invoke(tool_args)

            else:
                result = "Unknown intent."

            tool_results.append({"name": tool_name, "result": str(result)})

        except Exception as e:
            result = f"❌ Error running {tool_name}: {e}"
            tool_results.append({"name": tool_name, "result": result})

        # Step 3: Synthesise response with LLM
        llm = create_agent(model=model)

        synthesis_prompt = f"""The user asked: "{query}"

I used the tool `{tool_name}` and got this result:

{str(result)[:4000]}

Please provide a concise, helpful summary of this result for the user. 
Use Markdown formatting. Be direct — don't say "based on the tool output".
If there are code standards or reviews, highlight the most important ones."""

        system_msg = SYSTEM_PROMPT.format(
            org_name=settings.org_name,
            github_org=settings.github_org,
            default_repo=(
                settings.github_repos_list[0] if settings.github_repos_list else "N/A"
            ),
        )

        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=synthesis_prompt),
        ]

        try:
            response = llm.invoke(messages)
            final_text = response.content
        except Exception as e:
            # Fallback: return raw tool output on LLM failure
            final_text = str(result)

    else:
        # No intent matched — use LLM for general conversation
        llm = create_agent(model=model)

        system_msg = SYSTEM_PROMPT.format(
            org_name=settings.org_name,
            github_org=settings.github_org,
            default_repo=(
                settings.github_repos_list[0] if settings.github_repos_list else "N/A"
            ),
        )

        messages = [SystemMessage(content=system_msg)]
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=query))

        try:
            response = llm.invoke(messages)
            final_text = response.content
        except Exception as e:
            final_text = f"❌ Error: {e}"

    return {
        "response": final_text,
        "tool_calls": tool_calls_made,
        "tool_results": tool_results,
    }
