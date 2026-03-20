"""
agent.py — LangGraph agent with mode-aware prompts, emotion detection, and memory.
"""

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

import config
from tools import ALL_TOOLS
from prompts import get_prompt
from emotion import detect_emotion, build_emotion_prefix
from memory import checkpointer, get_session_summary, get_mode


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:   Annotated[list[BaseMessage], add_messages]
    session_id: str
    mode:       str


# ── LLM ───────────────────────────────────────────────────────────────────────

llm = ChatOllama(
    base_url=config.OLLAMA_BASE_URL,
    model=config.OLLAMA_MODEL,
    temperature=0.3,    # slight warmth for conversational tone
)
llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> AgentState:
    session_id = state.get("session_id", "default")
    mode       = state.get("mode", get_mode(session_id))

    # Get last user message for emotion detection
    user_messages = [m for m in state["messages"] if hasattr(m, "type") and m.type == "human"]
    last_user_msg = user_messages[-1].content if user_messages else ""

    # Build dynamic system prompt = base prompt + session context + emotion prefix
    emotion        = detect_emotion(last_user_msg)
    emotion_prefix = build_emotion_prefix(emotion)
    session_ctx    = get_session_summary(session_id)
    system_prompt  = get_prompt(mode) + session_ctx + emotion_prefix

    messages_with_system = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = llm_with_tools.invoke(messages_with_system)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph():
    tool_node = ToolNode(ALL_TOOLS)

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)

    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")

    return g.compile(checkpointer=checkpointer)


graph = build_graph()
