# ConfidenceOS — AI-Powered Interview Confidence Coach

![Status](https://img.shields.io/badge/status-portfolio%20project-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-yellow)
![Ollama](https://img.shields.io/badge/LLM-Ollama-orange)

> *Built by a job seeker, for job seekers — powered by local LLMs, RAG, and a knowledge graph.*

> ⭐ **This is a portfolio project.** Feel free to fork it, run it locally, and adapt it for your own use. Direct PRs are not actively reviewed but issues and feedback are always welcome!

Landing a great job is not just about skills — it is about showing up with clarity and confidence. **ConfidenceOS** is an end-to-end agentic AI application that acts as your personal interview coach, helping you reframe self-doubt, practice mock interviews, negotiate offers, and craft compelling answers — all grounded in real frameworks from cognitive behavioral therapy (CBT) and principled negotiation.

This project demonstrates a production-minded approach to building AI systems: modular architecture, retrieval-augmented generation (RAG) over a vector store, graph-based knowledge retrieval, multi-mode agentic reasoning, session memory, and emotion-aware responses — running entirely on your local machine at zero API cost.

---

## Why This Project

Most interview prep tools are static. ConfidenceOS is conversational, contextual, and adaptive:
- It **retrieves relevant knowledge** from indexed books using semantic search (Pinecone)
- It **traverses relationships** between concepts, frameworks, and techniques (Neo4j AuraDB)
- It **detects emotional tone** in your messages and adjusts its coaching style accordingly
- It **remembers your session** — your name, target role, and progress across the conversation
- It **switches between coaching modes** — from mock interviews to CBT reframing to salary negotiation

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM (local) | Ollama — llama3.2 |
| Embeddings | nomic-embed-text (768-dim) |
| Agent orchestration | LangGraph |
| Vector search | Pinecone |
| Knowledge graph | Neo4j AuraDB |
| Backend API | FastAPI |
| Frontend | React + Vite + Tailwind CSS |

---

## Project Structure

```
local-rag-agent/
├── .env                        ← your secret keys (never commit this)
├── chunk_texts/                ← local JSON files with chunk text
├── backend/
│   ├── config.py               ← reads all env vars
│   ├── prompts.py              ← ALL system prompts (edit freely)
│   ├── emotion.py              ← emotion detection logic
│   ├── memory.py               ← session memory + LangGraph checkpointer
│   ├── tools.py                ← all LangGraph tools
│   ├── agent.py                ← LangGraph graph definition
│   ├── main.py                 ← FastAPI app
│   └── requirements.txt
└── frontend/
    ├── .env                    ← VITE_API_URL
    └── src/
        └── App.jsx             ← React chat UI
```

---

## Agent Modes

| Mode | Icon | Description |
|---|---|---|
| General Chat | 💬 | Open conversation about career and job hunt |
| Mock Interview | 🎤 | Realistic interview Q&A with feedback |
| CBT Reframe | 🧠 | Reframe negative thoughts using CBT techniques |
| Negotiation | 💰 | Salary and offer negotiation coach |
| STAR Coach | ⭐ | Craft strong behavioral interview answers |

Each mode has its own system prompt in `prompts.py` — edit them freely without touching any code.

---

## How It Works

```
User message
    ↓
React UI sends message + session_id + mode
    ↓
FastAPI /chat endpoint
    ↓
emotion.py detects tone (distressed / positive / neutral)
    ↓
prompts.py loads mode-specific system prompt
memory.py injects session context (name, role, topics, confidence)
    ↓
LangGraph agent (Ollama LLM)
    ↓ (if tool needed)
Tools: search_pinecone | query_auradb | get_weather | say_hello | calculator
    ↓
LangGraph MemorySaver persists conversation across turns
    ↓
Reply returned to UI
```

---

## Prerequisites

1. **Ollama** — https://ollama.com
2. **Python 3.10+**
3. **Node.js 18+**
4. **Pinecone** account — https://pinecone.io
5. **Neo4j AuraDB** free instance — https://neo4j.com/cloud/aura

---

## Setup

### 1. Pull Ollama models
```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

### 2. Configure `.env`
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
PINECONE_API_KEY=your-key
PINECONE_INDEX_NAME=your-index
PINECONE_NAMESPACE=documents
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173
```

### 3. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Customising Prompts

All prompts live in `backend/prompts.py`. You can:
- Edit Aria's persona in the `PERSONA` string
- Change how each mode behaves in the `PROMPTS` dict
- Add a new mode by adding a key to `PROMPTS` and an entry to `get_available_modes()`

No code changes needed — just edit the text and restart the backend.

---

## Testing the App

**Test 1 — General chat:**
```
Tell me about yourself
```

**Test 2 — Mock interview (switch to 🎤 mode):**
```
Start a mock interview for a Senior Product Manager role
```

**Test 3 — CBT reframe (switch to 🧠 mode):**
```
I'm terrible at interviews, I always freeze up
```

**Test 4 — Negotiation (switch to 💰 mode):**
```
I got an offer for $120k but I was expecting $140k
```

**Test 5 — STAR coach (switch to ⭐ mode):**
```
Help me answer: tell me about a time you handled a conflict
```

**Test 6 — Pinecone RAG:**
```
What does the knowledge base say about handling anxiety?
```

**Test 7 — AuraDB graph:**
```
What techniques are used in CBT chunks?
```

> ✅ Tests 1–5 work immediately.
> ⚠️ Tests 6–7 require data in Pinecone and AuraDB.

---

## Contributing & Forking

This project is primarily a personal portfolio piece — see [CONTRIBUTING.md](./CONTRIBUTING.md) for full details.

**Short version:**
- Fork it freely and adapt it for your own use ✅
- Open issues for bugs or suggestions ✅
- Direct PRs are not actively reviewed ⚠️

If you build something cool on top of it, share it!

- **Add a new mode** → add to `PROMPTS` and `get_available_modes()` in `prompts.py`
- **Add a new tool** → define `@tool` in `tools.py`, add to `ALL_TOOLS`
- **Add streaming** → replace `graph.invoke()` with `graph.stream()` + FastAPI `StreamingResponse`
- **Add more books** → index chunks into Pinecone + add nodes to AuraDB
## Extending the App

---

## 🚧 Work in Progress

This project is actively being developed. The current version is a working foundation — here's what's coming next:

- **Cloud deployment** — migrate backend and vector infrastructure to AWS or GCP for production-grade reliability and scalability
- **Richer knowledge base** — index additional books, articles, and interview guides into Pinecone for deeper, more contextual coaching
- **Evaluation framework** — add automated quality scoring for agent responses, RAG retrieval accuracy, and answer relevance
- **UI overhaul** — improve the chat experience with better formatting, session history sidebar, progress tracking, and mobile responsiveness
- **MCP server integration** — connect to external tools via Model Context Protocol (calendar, LinkedIn, job boards) to make Aria aware of your real job hunt pipeline
- **Optimised retrieval layer** — improve RAG performance with hybrid search (dense + sparse), re-ranking, query expansion, and smarter chunk selection strategies

Contributions, feedback, and ideas are welcome!