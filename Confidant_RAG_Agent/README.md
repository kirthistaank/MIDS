# RAG + Knowledge Graph Chat App

A local, cost-free conversational AI app using:
- **Ollama** — runs the LLM on your machine (no API costs)
- **LangGraph** — orchestrates the agentic loop
- **Pinecone** — cloud vector store for semantic document search
- **Neo4j AuraDB** — cloud knowledge graph for relationship queries
- **FastAPI** — lightweight Python API server
- **React + Vite + Tailwind** — minimal chat UI

---

## Project Structure

```
project/
├── .env                  ← your secret keys (never commit this)
├── backend/
│   ├── config.py         ← reads all env vars (import here, not os.environ)
│   ├── tools.py          ← all LangGraph tools (Pinecone, AuraDB, helpers)
│   ├── agent.py          ← LangGraph graph definition
│   ├── main.py           ← FastAPI app with /chat and /health endpoints
│   └── requirements.txt
└── frontend/
    ├── .env              ← VITE_API_URL
    ├── src/
    │   └── App.jsx       ← React chat UI
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Prerequisites

1. **Ollama** installed — https://ollama.com
2. **Python 3.10+**
3. **Node.js 18+**
4. A **Pinecone** account with an index created — https://pinecone.io
5. A **Neo4j AuraDB** free instance — https://neo4j.com/cloud/aura

---

## Setup

### 1. Pull Ollama models

```bash
ollama pull llama3.2           # main chat model (~2GB)
ollama pull nomic-embed-text   # embedding model for Pinecone queries (~300MB)
ollama serve                   # start Ollama in the background
```

### 2. Configure environment variables

Copy `.env.example` to `.env` in the project root and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Where to find it |
|---|---|
| `PINECONE_API_KEY` | Pinecone console → API Keys |
| `PINECONE_INDEX_NAME` | The index you created |
| `PINECONE_NAMESPACE` | Optional; leave blank if unused |
| `NEO4J_URI` | AuraDB console → Connection URI |
| `NEO4J_PASSWORD` | Set when you created the AuraDB instance |


---

## Testing the App — Try These in Order

**Test 1 — Basic tool (instant response):**
```
Say hello to aibear
```

**Test 2 — Calculator tool:**
```
What is 123 multiplied by 456?
```

**Test 3 — Weather tool:**
```
What is the weather in Tokyo?
```

**Test 4 — Direct LLM (no tool, just Ollama thinking):**
```
Tell me a fun fact about artificial intelligence
```

**Test 5 — Pinecone RAG (tests your vector index):**
```
Search the knowledge base for [a topic you've indexed in Pinecone]
```

**Test 6 — AuraDB graph (tests your knowledge graph):**
```
1. Query the graph: MATCH (n) RETURN n.name LIMIT 5
2. Query the graph: MATCH (c:Concept) WHERE c.name =~ '.*CBT.*' RETURN c.name LIMIT 10
```

> ✅ Tests 1–4 should work immediately.  
> ⚠️ Tests 5–6 will only work if your Pinecone index and AuraDB have data in them.

---

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000/health — you should see `{"status":"ok"}`.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the chat UI loads.

---

## How the Agent Works (Step by Step)

```
User types a message
      ↓
React UI sends POST /chat with full message history
      ↓
FastAPI converts history to LangChain messages
      ↓
LangGraph "agent" node calls Ollama LLM
      ↓
LLM decides: answer directly OR call a tool?
      ↓ (tool call)
LangGraph "tools" node executes the tool:
  - search_pinecone   → embeds query, searches your vector index
  - query_auradb      → runs Cypher against your knowledge graph
  - get_weather       → demo stub
  - say_hello         → greets a name
  - calculator        → evaluates math
      ↓
Tool result is added to message history
      ↓
Back to "agent" node — LLM sees the result and writes a reply
      ↓
FastAPI returns { "reply": "..." }
      ↓
React displays the message
```

---

## Example Prompts to Try

| Prompt | Tool used |
|---|---|
| "What does the document say about X?" | `search_pinecone` |
| "Show me relationships between Person A and B" | `query_auradb` |
| "What is 456 * 789?" | `calculator` |
| "What's the weather in Tokyo?" | `get_weather` |
| "Hi, my name is Alice" | `say_hello` |
| "Tell me about quantum computing" | No tool (direct LLM answer) |


---

## Pinecone Setup Notes

Your index must use the **same dimension** as `nomic-embed-text` output, which is **768**.
When indexing your chunks (outside this project), store the chunk text in the metadata under the key `"text"`:

```python
index.upsert(vectors=[
    {"id": "chunk-1", "values": embedding, "metadata": {"text": "your chunk text here"}}
])
```

---

## AuraDB Setup Notes

- AuraDB free tier supports up to 200k nodes and 400k relationships.
- The `query_auradb` tool accepts raw Cypher from the LLM. In production, you'd want to validate or restrict the queries.
- Example graph schema to get started:

```cypher
CREATE (:Person {name: "Alice"})-[:KNOWS]->(:Person {name: "Bob"})
```

---

## Extending the App

- **Add streaming** — replace `graph.invoke()` with `graph.stream()` and use FastAPI's `StreamingResponse` + Server-Sent Events on the frontend.
- **Add memory** — use LangGraph's `MemorySaver` checkpointer to persist conversation across sessions.
- **Add more tools** — define a new `@tool` in `tools.py` and add it to `ALL_TOOLS`. The agent picks it up automatically.
- **Swap the model** — change `OLLAMA_MODEL=mistral` in `.env` for a different personality/size.
