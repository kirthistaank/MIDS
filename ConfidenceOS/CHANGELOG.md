# Changelog

All notable changes to ConfidenceOS are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] — 2026-03-20

### Added
- Five coaching modes: General Chat, Mock Interview, CBT Reframe, Negotiation, STAR Coach
- Voice input via Web Speech API in Mock Interview mode
- Live confidence scoreboard with STAR, Language, and Relevance sub-scores
- STAR Coach sidebar with common mistakes and clickable example questions
- Emotion detection — agent detects anxiety and adjusts tone accordingly
- LangGraph MemorySaver — session memory persists across conversation turns
- Pinecone RAG — semantic search over indexed book chunks
- Neo4j AuraDB — knowledge graph for relationship traversal
- Rotating file logger to `/tmp/confidenceos/` (128MB, 3 files max)
- Retrieval trace logging — every Pinecone chunk and AuraDB node logged
- Onboarding screen with mode descriptions and example prompts
- Help guide panel (`?` button) with scoring guide and keyboard shortcuts
- Landing page inspired by minimal dark AI product sites
- Geometric bot SVG icon (`BotIcon.jsx`) scalable at any size
- Matrix terminal theme throughout

### Changed
- Agent now builds system prompt dynamically per turn (mode + session + emotion)
- All prompts centralised in `prompts.py` — no prompts in logic code
- CORS opened to `*` for local development

---

## [1.0.0] — 2026-03-01

### Added
- Initial LangGraph hello-world agent with Ollama
- Basic tool calling: `get_weather`, `say_hello`, `calculator`
- FastAPI backend with `/chat` and `/health` endpoints
- React + Vite + Tailwind chat UI
- Pinecone vector search tool
- Neo4j AuraDB Cypher query tool
- `config.py` for centralised environment variable management