"""
main.py — FastAPI entry point.
Run with: uvicorn main:app --reload --port 8000
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

import config
from agent import graph
from memory import get_session, set_mode, update_session
from prompts import get_available_modes
from logger import get_logger

log = get_logger(__name__)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="ConfidenceOS — Interview Confidence Coach API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str
    content: str

class ChatRequest(BaseModel):
    messages:   list[ChatMessage]
    session_id: str = "default"
    mode:       str = "chat"

class ChatResponse(BaseModel):
    reply:      str
    session_id: str
    mode:       str

class ModeRequest(BaseModel):
    session_id: str = "default"
    mode:       str

class SessionUpdateRequest(BaseModel):
    session_id:  str = "default"
    user_name:   str | None = None
    target_role: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": config.OLLAMA_MODEL, "version": "2.0.0"}


@app.get("/modes")
def get_modes():
    """Return available agent modes for the UI mode switcher."""
    return {"modes": get_available_modes()}


@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    """Return current session state."""
    return get_session(session_id)


@app.post("/session/update")
def update_session_info(req: SessionUpdateRequest):
    """Update session metadata like user name or target role."""
    updates = {}
    if req.user_name:
        updates["user_name"] = req.user_name
    if req.target_role:
        updates["target_role"] = req.target_role
    from memory import update_session
    return update_session(req.session_id, updates)


@app.post("/mode")
def switch_mode(req: ModeRequest):
    """Switch the agent mode for a session."""
    session = set_mode(req.session_id, req.mode)
    return {"session_id": req.session_id, "mode": req.mode}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    log.info("Chat request | session=%s | mode=%s | messages=%d",
             req.session_id, req.mode, len(req.messages))

    set_mode(req.session_id, req.mode)

    lc_messages = []
    for m in req.messages:
        if m.role == "user":
            lc_messages.append(HumanMessage(content=m.content))
        else:
            lc_messages.append(AIMessage(content=m.content))

    try:
        result = graph.invoke(
            {"messages": lc_messages, "session_id": req.session_id, "mode": req.mode},
            config={"configurable": {"thread_id": req.session_id}},
        )
        reply = result["messages"][-1].content
        log.info("Chat response sent | session=%s | reply_len=%d", req.session_id, len(reply))
        return ChatResponse(reply=reply, session_id=req.session_id, mode=req.mode)
    except Exception as e:
        log.error("Chat failed | session=%s | error=%s", req.session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.APP_HOST, port=config.APP_PORT, reload=True)
