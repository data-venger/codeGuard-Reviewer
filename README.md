# CodeGuard — RAG-Based PR Reviewer

**Org-aware, local-first AI code review** powered by Retrieval Augmented Generation.

Runs entirely on your Mac M4 (8 GB) — no code or context is ever sent to an external API.

---

## Architecture

| Component | Technology | RAM Budget |
|-----------|-----------|------------|
| LLM Engine | Qwen2.5-Coder-7B-Instruct (Q4_K_M) via Ollama | ~5.0 GB |
| Embeddings | snowflake-arctic-embed-m-v1.5 via FastEmbed | ~500 MB |
| Vector DB | Qdrant (Docker, local) | ≤1.0 GB |
| Tickets | Plane REST API | — |
| Code Source | GitHub REST API | — |
| Orchestration | LangChain | — |
| UI | Streamlit | ~200 MB |

### Six Context Layers

1. **Ticket Intent** — Plane issues (what the PR should achieve)
2. **Coding Standards** — Markdown rule sets (what patterns to enforce)
3. **ADRs** — Architecture decisions (what patterns are mandated/forbidden)
4. **Historical Reviews** — Past PR comments (what has been flagged before)
5. **Codebase Context** — Module summaries (what the code does)
6. **Author Context** — Developer profiles (how verbose to be)

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker Desktop** (for Qdrant)
- **Ollama** (for Phase 2)

### Setup

```bash
# 1. Clone and enter project
cd RAG-Based-PR-Review

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env with your Plane API token, GitHub token, org, repos

# 5. Start Qdrant
docker compose up -d

# 6. Initialise collections
python scripts/init_qdrant.py

# 7. Run ingestion
python scripts/ingest.py all
```

### Ingestion Commands

```bash
python scripts/ingest.py all          # Run all pipelines
python scripts/ingest.py standards    # Coding standards only
python scripts/ingest.py adrs         # ADRs only
python scripts/ingest.py tickets      # Plane tickets only
python scripts/ingest.py history      # GitHub PR history only
python scripts/ingest.py authors      # Author profiles only
python scripts/ingest.py codebase /path/to/repo  # Codebase context
```

### Running Tests

```bash
# Unit tests (no Qdrant required)
pytest tests/test_chunker.py -v

# Embedding tests (downloads model on first run)
pytest tests/test_embeddings.py -v

# Integration tests (requires Qdrant running)
pytest tests/test_qdrant_client.py -v
pytest tests/test_ingestion.py -v

# All tests
pytest tests/ -v
```

---

## Project Structure

```
RAG-Based-PR-Review/
├── docker-compose.yml          # Qdrant service
├── pyproject.toml              # Project config
├── requirements.txt            # Dependencies
├── .env.example                # Env var template
├── config/
│   └── settings.py             # Pydantic Settings
├── codeguard/
│   ├── embeddings.py           # FastEmbed wrapper
│   ├── qdrant_store.py         # Qdrant operations
│   ├── chunker.py              # Text chunking strategies
│   ├── github_client.py        # GitHub API client
│   ├── plane_client.py         # Plane API client
│   └── ingestion/
│       ├── tickets.py          # Layer 1: Plane tickets
│       ├── standards.py        # Layer 2: Coding standards
│       ├── adrs.py             # Layer 3: ADRs
│       ├── history.py          # Layer 4: PR review history
│       ├── codebase.py         # Layer 5: Module summaries
│       └── authors.py          # Layer 6: Author profiles
├── data/
│   ├── standards/              # Your coding standards (.md)
│   ├── adrs/                   # Your ADR files (.md)
│   └── authors.yaml            # Author metadata
├── scripts/
│   ├── init_qdrant.py          # Collection initialisation
│   └── ingest.py               # Ingestion CLI
└── tests/                      # Test suite
```

---

## Implementation Status

- [x] **Phase 0**: Project scaffold & infrastructure
- [x] **Phase 1**: Context ingestion foundation (6 layers)
- [ ] **Phase 2**: Review loop MVP (Ollama + RAG + Streamlit)
- [ ] **Phase 3**: Agentic NL interface (LangChain agent)
- [ ] **Phase 4**: Feedback loop & scoring
- [ ] **Phase 5**: Hardening & scheduling

---

*CodeGuard | Data Platform Engineering | v0.1.0*
