# AI Private Coach

This folder contains work on an **AI-powered private coach** — systems that analyze conversations (audio and transcripts) and deliver personalized, evidence-based feedback using large language models and retrieval-augmented generation (RAG).

## Contents

| Path | Description |
|------|-------------|
| [`GuidePost/`](GuidePost/) | MIDS capstone implementation — interpersonal dynamics coaching (audio analysis, hybrid RAG, knowledge graph retrieval). See [`GuidePost/README.md`](GuidePost/README.md) for project overview and setup. |

## Overview

The coach ingests meeting or conversation recordings, transcribes and structures the dialogue, retrieves relevant coaching frameworks and concepts, and generates actionable feedback on communication patterns, clarity, and interaction dynamics.

Typical pipeline:

```
Audio / transcript → speech-to-text & diarization → chunking & embeddings → vector + graph retrieval → LLM coaching output
```

What this project about : 
This project demonstrates my ability to design and deploy production-ready GenAI systems, combining LLMs, RAG, and scalable data pipelines — aligning with modern AI engineering requirements.

## Tech stack (high level)

- **LLMs** — GPT / open models via API or local inference  
- **RAG** — LangChain, vector stores (e.g. FAISS, Pinecone), optional Neo4j knowledge graph  
- **Audio** — Whisper, speaker diarization  
- **Backend / UI** — FastAPI, Streamlit or React (per subproject)

## Getting started

Open the subproject you need (currently **GuidePost**) and follow its README and `GuidePostPythonContainer/` setup instructions for dependencies, environment variables, and local run steps.
