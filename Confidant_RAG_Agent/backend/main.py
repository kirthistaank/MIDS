"""
main.py — FastAPI entry point.
Run with:  uvicorn main:app --reload --port 8000
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

import config
from agent import graph


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="RAG + KG Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # open for local dev — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]   # full conversation history from the UI

class ChatResponse(BaseModel):
    reply: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": config.OLLAMA_MODEL}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Accepts the full message history from the React UI,
    runs the LangGraph agent, and returns the assistant reply.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    # Convert to LangChain message objects
    lc_messages = []
    for m in req.messages:
        if m.role == "user":
            lc_messages.append(HumanMessage(content=m.content))
        else:
            lc_messages.append(AIMessage(content=m.content))

    try:
        result = graph.invoke({"messages": lc_messages})
        reply  = result["messages"][-1].content
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.APP_HOST, port=config.APP_PORT, reload=True)
