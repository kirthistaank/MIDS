# Aria — Interview Confidence Coach

A local, cost-free AI-powered interview coach using:
- **Ollama** — runs the LLM on your machine (no API costs)
- **LangGraph** — orchestrates the agentic loop with memory
- **Pinecone** — cloud vector store for semantic document search
- **Neo4j AuraDB** — cloud knowledge graph for relationship queries
- **FastAPI** — lightweight Python API server
- **React + Vite + Tailwind** — chat UI with mode switcher and confidence meter

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

## Extending the App

- **Add a new mode** → add to `PROMPTS` and `get_available_modes()` in `prompts.py`
- **Add a new tool** → define `@tool` in `tools.py`, add to `ALL_TOOLS`
- **Add streaming** → replace `graph.invoke()` with `graph.stream()` + FastAPI `StreamingResponse`
- **Add more books** → index chunks into Pinecone + add nodes to AuraDB
- **Persist memory** → swap `MemorySaver` in `memory.py` for Redis or SQLite checkpointer
