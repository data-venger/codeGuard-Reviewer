# 🛡️ CodeGuard — AI-Powered PR Reviewer

<div align="center">

**Automated code reviews powered by RAG + LLM, using your team's own standards, architecture decisions, and review history.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black.svg)](https://ollama.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC382D.svg)](https://qdrant.tech)

</div>

---

## 🎯 What is CodeGuard?

CodeGuard is an **AI-powered Pull Request reviewer** that goes beyond generic linting. It uses **Retrieval-Augmented Generation (RAG)** to review PRs against your organisation's actual context:

| Context Layer | Source | Purpose |
|---------------|--------|---------|
| 🎫 **Ticket Intent** | Plane API | Does the PR fulfil the ticket requirements? |
| 📏 **Coding Standards** | Markdown files | Does the code follow your naming conventions, style guides? |
| 🏛️ **Architecture Decisions** | ADR documents | Does the code violate design decisions (ADRs)? |
| 📜 **Review History** | Past AI reviews | Are the same issues recurring across PRs? |
| 💻 **Codebase Context** | Your repository | Does the change fit the existing codebase patterns? |
| 👤 **Author Context** | YAML profiles | How experienced is this developer? Adjust feedback accordingly. |

### Key Features

- **📊 Scorecard** — Code quality %, standards compliance %, architecture score, and merge recommendation (✅ Merge / ⚠️ Improve / ❌ Block)
- **💬 Chat Interface** — Ask natural language questions about your standards, ADRs, and past reviews
- **🔍 Streaming Reviews** — Watch the AI review generate in real-time
- **🧠 6-Layer RAG** — Context from tickets, standards, ADRs, history, codebase, and author profiles
- **🏠 Fully Local** — Runs on your machine with Ollama (no API keys to OpenAI needed)

---

## 📸 Screenshots

### Review Scorecard
The scorecard shows code quality percentages with color-coded bars, a letter grade, merge recommendation, and issue breakdown:

- **📊 Code Quality** — Overall quality score (green/yellow/red)
- **📏 Standards Compliance** — Rule adherence percentage
- **🏛️ Architecture** — ADR compliance
- **🛡️ Bug Safety** — Risk assessment
- **Letter Grade** — A through F
- **Merge Decision** — ✅ Ready / ⚠️ Needs Work / ❌ Block

### Chat Interface
Ask questions like:
- *"What are our Python naming conventions?"*
- *"Show me open PRs"*
- *"Were there past reviews about error handling?"*

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit Web App                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │Browse PRs│  │  Review Tab  │  │     Chat Tab          │  │
│  │  (List)  │  │  + Scorecard │  │  (LangChain Agent)    │  │
│  └────┬─────┘  └──────┬───────┘  └───────────┬───────────┘  │
├───────┼────────────────┼──────────────────────┼──────────────┤
│       ▼                ▼                      ▼              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │               Review Engine                          │     │
│  │  GitHub Diff → RAG Retriever → LLM → Scorecard      │     │
│  └──────────────────────┬──────────────────────────────┘     │
│                         ▼                                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │             6-Layer RAG Retriever                    │     │
│  │  tickets │ standards │ ADRs │ history │ code │ author│     │
│  └──────────────────────┬──────────────────────────────┘     │
│                         ▼                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Qdrant DB   │  │   Ollama     │  │   GitHub API     │   │
│  │ (Vectors)    │  │   (LLM)      │  │  (PRs & Diffs)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **Docker** | 20+ | Runs Qdrant vector database |
| **Ollama** | Latest | Runs local LLM (qwen2.5-coder) |
| **Git** | Any | Clone the repo |

### 1. Clone & Setup

```bash
git clone https://github.com/data-venger/RAG-Based-PR-Review.git
cd RAG-Based-PR-Review

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# ── Plane (Ticket Source) ──
PLANE_API_TOKEN=your_plane_api_token
PLANE_BASE_URL=https://api.plane.so/api/v1
PLANE_WORKSPACE_SLUG=your-workspace

# ── GitHub ──
GITHUB_TOKEN=ghp_your_github_token
GITHUB_ORG=your-org
GITHUB_REPOS=repo1,repo2

# ── Qdrant ──
QDRANT_HOST=localhost
QDRANT_PORT=6333

# ── Organisation ──
ORG_NAME=Your Company Name
```

<details>
<summary><b>How to get API tokens</b></summary>

**GitHub Token:**
1. Go to [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Generate a token with `repo` scope
3. Copy the `ghp_...` token

**Plane API Token:**
1. Log into your Plane workspace
2. Go to **Settings → API Tokens**
3. Create a new token and copy it

</details>

### 3. Start Services

```bash
# Start Qdrant (vector database)
docker-compose up -d

# Pull the LLM model
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

### 4. Initialize & Ingest

```bash
# Create Qdrant collections
python scripts/init_qdrant.py

# Ingest all context layers
python scripts/ingest.py all
```

You can also ingest layers individually:

```bash
python scripts/ingest.py standards    # Coding standards
python scripts/ingest.py adrs         # Architecture decisions
python scripts/ingest.py tickets      # Plane tickets
python scripts/ingest.py history      # Past reviews
python scripts/ingest.py codebase     # Repository code
python scripts/ingest.py authors      # Developer profiles
```

### 5. Launch the App

```bash
streamlit run app/streamlit_app.py
```

Open **http://localhost:8501** in your browser.

---

## 📂 Project Structure

```
RAG-Based-PR-Review/
├── app/                          # Streamlit UI
│   ├── streamlit_app.py          # Main app (3 tabs: Browse, Review, Chat)
│   ├── chat_tab.py               # Chat interface
│   ├── components.py             # Reusable UI components
│   └── scorecard_ui.py           # Visual scorecard rendering
│
├── codeguard/                    # Core library
│   ├── agent/                    # LangChain agent (Chat tab)
│   │   ├── agent.py              # Intent-based routing engine
│   │   ├── tools.py              # 5 agent tools (PRs, search, review)
│   │   └── prompts.py            # System prompts
│   │
│   ├── ingestion/                # Data ingestion pipelines
│   │   ├── standards.py          # Layer 2: Coding standards
│   │   ├── adrs.py               # Layer 3: Architecture decisions
│   │   ├── tickets.py            # Layer 1: Plane tickets
│   │   ├── history.py            # Layer 4: Past reviews
│   │   ├── codebase.py           # Layer 5: Repository code
│   │   └── authors.py            # Layer 6: Author profiles
│   │
│   ├── chunker.py                # Smart text chunking engine
│   ├── embeddings.py             # FastEmbed wrapper (Arctic-M)
│   ├── github_client.py          # GitHub REST API client
│   ├── llm_client.py             # Ollama LLM client
│   ├── plane_client.py           # Plane REST API client
│   ├── qdrant_store.py           # Qdrant vector store manager
│   ├── retriever.py              # 6-layer RAG retriever
│   ├── review_engine.py          # Full review orchestration
│   ├── scorecard.py              # Review scoring engine
│   └── ticket_extractor.py       # Ticket ID extraction from branches
│
├── config/
│   └── settings.py               # Pydantic settings (loads .env)
│
├── data/                         # Org-specific context
│   ├── standards/                # Your coding standards (Markdown)
│   ├── adrs/                     # Architecture Decision Records
│   └── authors.yaml              # Developer profiles
│
├── scripts/
│   ├── init_qdrant.py            # Create Qdrant collections
│   └── ingest.py                 # CLI for data ingestion
│
├── tests/                        # Unit tests (46 passing)
│   ├── test_chunker.py
│   ├── test_embeddings.py
│   ├── test_ingestion.py
│   ├── test_qdrant_client.py
│   └── test_review.py
│
├── docker-compose.yml            # Qdrant container
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Project metadata
├── .env.example                  # Environment template
└── .gitignore
```

---

## 🧪 Running Tests

```bash
# Run all 46 tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_chunker.py -v
```

---

## 🔧 Customisation

### Adding Coding Standards

Create Markdown files in `data/standards/`:

```markdown
# Python Naming Conventions

## Rules
- Module-level variables: `UPPER_SNAKE_CASE`
- Classes: `PascalCase`
- Functions: `snake_case`
- Private methods: prefix with `_`
```

### Adding Architecture Decisions

Create ADR files in `data/adrs/`:

```markdown
# ADR-001: Repository Pattern

## Status: Accepted

## Decision
All database access must go through repository classes.

## Rules
- No raw SQL in service classes
- Repository classes handle all ORM logic
```

### Adding Author Profiles

Edit `data/authors.yaml`:

```yaml
joker:
  level: senior
  focus_areas: [backend, architecture]
  guidance: "This developer is experienced — focus on architectural concerns."

new_dev:
  level: junior
  focus_areas: [frontend]
  guidance: "Provide detailed explanations and code examples."
```

After adding/modifying data, re-run ingestion:

```bash
python scripts/ingest.py all
```

---

## 🛠️ Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| **Frontend** | Streamlit | Web UI with 3 tabs |
| **LLM** | Ollama (qwen2.5-coder 7B) | Local code review generation |
| **Vector DB** | Qdrant | Store & search embeddings |
| **Embeddings** | FastEmbed (Arctic-M 768d) | Convert text to vectors |
| **RAG Framework** | LangChain | Agent tools & orchestration |
| **Tickets** | Plane REST API | Project management integration |
| **Code Hosting** | GitHub REST API | PR metadata & diffs |
| **Config** | Pydantic Settings | Type-safe .env loading |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">
  <b>Built with ❤️ by the Data Venger team</b>
</div>
